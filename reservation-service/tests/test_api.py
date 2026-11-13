from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from conftest import auth

SHOWTIME = 10


def hold(client, user, seats, showtime=SHOWTIME):
    return client.post("/holds", json={"showtime_id": showtime, "seats": seats}, headers=auth(user))


def seat_status(client, label, showtime=SHOWTIME, user=None):
    headers = auth(user) if user else {}
    seats = client.get(f"/showtimes/{showtime}/seats", headers=headers).json()["seats"]
    return next(s for s in seats if s["label"] == label)


# ---- basics -------------------------------------------------------------------------------
def test_health(client):
    assert client.get("/health").json()["status"] == "ok"
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["database"] == "up"


def test_empty_seat_map_is_public_and_fully_available(client):
    r = client.get(f"/showtimes/{SHOWTIME}/seats")
    assert r.status_code == 200
    body = r.json()
    assert len(body["seats"]) == 96
    assert all(s["status"] == "available" for s in body["seats"])


def test_availability_single_and_many(client):
    assert hold(client, 1, ["A1", "A2"]).status_code == 201
    one = client.get(f"/showtimes/{SHOWTIME}/availability").json()
    assert (one["total"], one["held"], one["available"]) == (96, 2, 94)
    many = client.get("/showtimes/availability?ids=10,11").json()["showtimes"]
    assert [x["showtime_id"] for x in many] == [10, 11]
    assert many[1]["available"] == 96


# ---- holds --------------------------------------------------------------------------------
def test_hold_requires_login(client):
    r = client.post("/holds", json={"showtime_id": SHOWTIME, "seats": ["A1"]})
    assert r.status_code == 401


def test_create_hold_marks_seats_held_and_mine(client):
    r = hold(client, 1, ["b3", "B4"])
    assert r.status_code == 201
    body = r.json()
    assert body["seats"] == ["B3", "B4"] and body["status"] == "active"
    assert body["total"] == 16.0 and 0 < body["seconds_left"] <= 600
    assert seat_status(client, "B3")["status"] == "held"
    assert seat_status(client, "B3")["mine"] is False
    assert seat_status(client, "B3", user=1)["mine"] is True


def test_second_user_cannot_take_held_seat(client):
    assert hold(client, 1, ["C5", "C6"]).status_code == 201
    r = hold(client, 2, ["C6", "C7"])
    assert r.status_code == 409
    assert r.json()["detail"]["unavailable_seats"] == ["C6"]
    assert seat_status(client, "C7")["status"] == "available"   # nothing partially locked


def test_invalid_and_out_of_hall_seats(client):
    assert hold(client, 1, ["nonsense"]).status_code == 422
    assert hold(client, 1, ["Z99"]).status_code == 422
    assert hold(client, 1, ["A1", "A1"]).status_code == 422


def test_max_seats_per_hold(client):
    seats = [f"A{n}" for n in range(1, 10)]   # 9 > default limit of 8
    assert hold(client, 1, seats).status_code == 422


def test_reselecting_replaces_previous_hold(client):
    first = hold(client, 1, ["D1", "D2"]).json()
    second = hold(client, 1, ["D2", "D3"])
    assert second.status_code == 201
    assert seat_status(client, "D1")["status"] == "available"
    assert client.get(f"/holds/{first['id']}", headers=auth(1)).json()["status"] == "released"


def test_release_hold_frees_seats(client):
    h = hold(client, 1, ["E1"]).json()
    r = client.delete(f"/holds/{h['id']}", headers=auth(1))
    assert r.status_code == 200 and r.json()["status"] == "released"
    assert seat_status(client, "E1")["status"] == "available"


def test_cannot_see_someone_elses_hold(client):
    h = hold(client, 1, ["E1"]).json()
    assert client.get(f"/holds/{h['id']}", headers=auth(2)).status_code == 404


def test_expired_hold_frees_seats_and_cannot_be_confirmed(client, db_exec):
    h = hold(client, 1, ["F1", "F2"]).json()
    db_exec("UPDATE holds SET created_at = now() - interval '1 hour', expires_at = now() - interval '1 second'")
    assert seat_status(client, "F1")["status"] == "available"        # visible immediately
    assert hold(client, 2, ["F1"]).status_code == 201                # and really claimable
    assert client.post(f"/holds/{h['id']}/confirm", headers=auth(1)).status_code == 410


# ---- bookings -----------------------------------------------------------------------------
def test_confirm_creates_booking_and_is_idempotent(client):
    h = hold(client, 1, ["G1", "G2", "G3"]).json()
    r = client.post(f"/holds/{h['id']}/confirm", json={"payment_ref": "PAY-1"}, headers=auth(1))
    assert r.status_code == 201
    b = r.json()
    assert b["status"] == "confirmed" and b["seats"] == ["G1", "G2", "G3"]
    assert b["total_amount"] == 24.0 and b["payment_ref"] == "PAY-1"
    assert seat_status(client, "G1")["status"] == "booked"
    again = client.post(f"/holds/{h['id']}/confirm", headers=auth(1))
    assert again.json()["id"] == b["id"]
    assert len(client.get("/bookings", headers=auth(1)).json()["bookings"]) == 1


def test_booking_endpoint_alias(client):
    h = hold(client, 1, ["H1"]).json()
    r = client.post("/bookings", json={"hold_id": h["id"]}, headers=auth(1))
    assert r.status_code == 201 and r.json()["seats"] == ["H1"]


def test_cannot_confirm_someone_elses_hold(client):
    h = hold(client, 1, ["A1"]).json()
    assert client.post(f"/holds/{h['id']}/confirm", headers=auth(2)).status_code == 404


def test_booked_seat_cannot_be_held_again(client):
    h = hold(client, 1, ["A1"]).json()
    client.post(f"/holds/{h['id']}/confirm", headers=auth(1))
    assert hold(client, 2, ["A1"]).status_code == 409


def test_cancel_booking_frees_seats(client):
    h = hold(client, 1, ["A1", "A2"]).json()
    b = client.post(f"/holds/{h['id']}/confirm", headers=auth(1)).json()
    assert client.post(f"/bookings/{b['id']}/cancel", headers=auth(2)).status_code == 404
    r = client.post(f"/bookings/{b['id']}/cancel", headers=auth(1))
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert r.json()["seats"] == ["A1", "A2"]                           # history is kept
    assert seat_status(client, "A1")["status"] == "available"
    assert hold(client, 2, ["A1"]).status_code == 201


def test_my_bookings_only_shows_my_own(client):
    for user, seat in ((1, "A1"), (2, "A2")):
        h = hold(client, user, [seat]).json()
        client.post(f"/holds/{h['id']}/confirm", headers=auth(user))
    mine = client.get("/bookings", headers=auth(1)).json()["bookings"]
    assert [b["seats"] for b in mine] == [["A1"]]


# ---- suggestions --------------------------------------------------------------------------
def test_suggestions_are_adjacent_free_and_non_overlapping(client):
    hold(client, 1, ["E6", "E7"])
    r = client.get(f"/showtimes/{SHOWTIME}/suggest?count=3").json()
    seen = set()
    assert len(r["suggestions"]) == 3
    for s in r["suggestions"]:
        nums = [int(x[1:]) for x in s["seats"]]
        assert nums == list(range(nums[0], nums[0] + 3))
        assert not seen.intersection(s["seats"]) and not {"E6", "E7"} & set(s["seats"])
        seen.update(s["seats"])


# ---- admin --------------------------------------------------------------------------------
def test_admin_endpoints_require_admin(client):
    assert client.get("/admin/stats").status_code == 401
    assert client.get("/admin/stats", headers=auth(1)).status_code == 403


def test_admin_stats_lists_and_cancel(client):
    h = hold(client, 1, ["A1", "A2"]).json()
    b = client.post(f"/holds/{h['id']}/confirm", headers=auth(1)).json()
    hold(client, 2, ["B1"])
    admin = auth(99, "admin")
    stats = client.get("/admin/stats", headers=admin).json()
    assert (stats["confirmed_bookings"], stats["seats_sold"], stats["active_holds"]) == (1, 2, 1)
    assert stats["revenue"] == 16.0 and stats["top_showtimes"][0]["showtime_id"] == SHOWTIME
    assert len(client.get("/admin/bookings?status=confirmed", headers=admin).json()["bookings"]) == 1
    assert len(client.get("/admin/holds", headers=admin).json()["holds"]) == 1
    cancelled = client.post(f"/admin/bookings/{b['id']}/cancel", headers=admin).json()
    assert cancelled["status"] == "cancelled"


# ---- the important one: concurrency -------------------------------------------------------
def test_race_for_the_same_seat_has_exactly_one_winner(client):
    def attempt(user):
        return TestClient(client.app).post(
            "/holds", json={"showtime_id": SHOWTIME, "seats": ["A1"]}, headers=auth(user)
        ).status_code

    with ThreadPoolExecutor(max_workers=10) as pool:
        codes = list(pool.map(attempt, range(100, 110)))
    assert codes.count(201) == 1
    assert codes.count(409) == 9


# ---- startup schema (what replicas do when the container starts) --------------------------
def test_apply_schema_is_repeatable_and_replica_safe(client):
    import db
    from concurrent.futures import ThreadPoolExecutor as Pool

    db.apply_schema()
    db.apply_schema()                                    # repeating is harmless
    with db.get_conn() as conn:                          # simulate a brand-new database
        conn.execute("DROP TABLE seat_claims, bookings, holds CASCADE")
    with Pool(max_workers=4) as pool:                    # four "replicas" starting at once
        list(pool.map(lambda _: db.apply_schema(), range(4)))
    assert hold(client, 1, ["A1"]).status_code == 201    # tables are back and working
