"""Functional tests for the Movie Service."""

from __future__ import annotations

from datetime import date, timedelta


def test_health_reports_seeded_catalog(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] is True
    assert body["movies"] >= 20


def test_list_movies_returns_real_catalog(client):
    response = client.get("/movies")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 20
    titles = {movie["title"] for movie in body["items"]}
    assert "Inception" in titles
    assert "Parasite" in titles
    assert "Les Chevaux de Dieu" in titles
    first = body["items"][0]
    assert first["poster_url"].startswith("/media/posters/")
    assert first["genres"]


def test_filter_by_genre_and_mood(client):
    animation = client.get("/movies", params={"genre": "animation"}).json()
    assert animation["total"] >= 2
    assert all("Animation" in movie["genres"] for movie in animation["items"])

    romantic = client.get("/movies", params={"mood": "romantic"}).json()
    assert romantic["total"] >= 1
    assert all("romantic" in movie["moods"] for movie in romantic["items"])


def test_search_and_detail_by_slug(client):
    found = client.get("/movies", params={"q": "parasite"}).json()
    assert found["total"] == 1

    detail = client.get("/movies/inception")
    assert detail.status_code == 200
    body = detail.json()
    assert body["slug"] == "inception"
    assert body["release_year"] == 2010
    assert body["director"] == "Christopher Nolan"


def test_movie_showtimes_are_seeded(client):
    response = client.get("/movies/dune-part-two/showtimes")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] > 0
    showtime = body["items"][0]
    assert showtime["starts_at"].endswith("Z")
    assert showtime["price"] > 0
    assert showtime["hall"] is not None
    assert showtime["cinema"] is not None


def test_showtimes_filtered_by_day(client):
    today = date.today()
    response = client.get("/showtimes", params={"date": today.isoformat()})
    assert response.status_code == 200
    assert response.json()["total"] > 0

    tomorrow = client.get("/showtimes", params={"date": (today + timedelta(days=2)).isoformat()})
    assert tomorrow.status_code == 200
    assert tomorrow.json()["total"] > 0


def test_hall_layout_is_complete(client):
    halls = client.get("/halls").json()
    assert halls["total"] >= 8

    hall = halls["items"][0]
    layout = client.get(f"/halls/{hall['id']}/layout")
    assert layout.status_code == 200
    body = layout.json()
    assert body["rows"] == len(body["layout"])
    assert body["row_labels"][0] == "A"
    assert len(body["layout"][0]["seats"]) == body["seats_per_row"]
    assert body["total_seats"] <= body["rows"] * body["seats_per_row"]


def test_poster_falls_back_to_generated_svg(client):
    response = client.get("/media/posters/les-chevaux-de-dieu.jpg")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert b"Chevaux" in response.content
    assert b"MYCIMA" in response.content


def test_unknown_movie_returns_404(client):
    assert client.get("/movies/does-not-exist").status_code == 404


def test_admin_requires_token(client):
    response = client.post("/admin/movies", json={"title": "Test", "release_year": 2024})
    assert response.status_code == 401


def test_admin_can_create_update_and_delete_movie(client, admin_headers):
    payload = {
        "title": "Le Grand Voyage",
        "release_year": 2004,
        "director": "Ismaël Ferroukhi",
        "genres": ["Drama"],
        "moods": ["emotional", "thought-provoking"],
        "duration_minutes": 108,
        "rating": 7.6,
        "language": "French",
        "country": "Morocco",
    }
    created = client.post("/admin/movies", json=payload, headers=admin_headers)
    assert created.status_code == 201
    movie = created.json()
    assert movie["slug"] == "le-grand-voyage"

    duplicate = client.post("/admin/movies", json=payload, headers=admin_headers)
    assert duplicate.status_code == 409

    updated = client.patch(
        f"/admin/movies/{movie['id']}", json={"rating": 8.1}, headers=admin_headers
    )
    assert updated.status_code == 200
    assert updated.json()["rating"] == 8.1

    assert client.get("/movies", params={"genre": "Drama", "q": "voyage"}).json()["total"] == 1

    deleted = client.delete(f"/admin/movies/{movie['id']}", headers=admin_headers)
    assert deleted.status_code == 204
    assert client.get("/movies/le-grand-voyage").status_code == 404
