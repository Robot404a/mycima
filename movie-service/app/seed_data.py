"""Seed catalog: real cinemas in Morocco and real films.

Poster paths are TMDB CDN paths. The service downloads them on first request and
caches them locally; when a poster is unavailable the service generates an SVG
placeholder instead, so the catalog always renders.
"""

from __future__ import annotations

CINEMAS = [
    {
        "name": "Megarama Casablanca",
        "city": "Casablanca",
        "address": "Boulevard Al Qods, Sidi Maârouf",
        "phone": "+212 522 97 90 00",
    },
    {
        "name": "Pathé Californie",
        "city": "Casablanca",
        "address": "Boulevard Ghandi, Californie",
        "phone": "+212 522 25 66 66",
    },
    {
        "name": "Cinéma Rif",
        "city": "Casablanca",
        "address": "Boulevard Mohammed V, Centre-ville",
        "phone": "+212 522 22 27 27",
    },
    {
        "name": "Megarama Marrakech",
        "city": "Marrakech",
        "address": "Route de Casablanca, Zone Agdal",
        "phone": "+212 524 42 00 00",
    },
    {
        "name": "Cinéma Le Colisée",
        "city": "Rabat",
        "address": "Avenue Mohammed V",
        "phone": "+212 537 70 12 12",
    },
]

HALLS = [
    {
        "cinema": "Megarama Casablanca",
        "name": "Salle 1 - IMAX",
        "screen_type": "imax",
        "rows": 14,
        "seats_per_row": 22,
        "aisle_after": [4, 18],
        "broken_seats": ["G7", "G8"],
    },
    {
        "cinema": "Megarama Casablanca",
        "name": "Salle 2",
        "screen_type": "standard",
        "rows": 10,
        "seats_per_row": 16,
        "aisle_after": [2, 14],
        "broken_seats": [],
    },
    {
        "cinema": "Megarama Casablanca",
        "name": "Salle 3 - Premium",
        "screen_type": "premium",
        "rows": 8,
        "seats_per_row": 12,
        "aisle_after": [2, 10],
        "broken_seats": [],
    },
    {
        "cinema": "Pathé Californie",
        "name": "Salle 1",
        "screen_type": "standard",
        "rows": 12,
        "seats_per_row": 18,
        "aisle_after": [2, 16],
        "broken_seats": [],
    },
    {
        "cinema": "Pathé Californie",
        "name": "Salle 2",
        "screen_type": "standard",
        "rows": 9,
        "seats_per_row": 14,
        "aisle_after": [2, 12],
        "broken_seats": ["E1"],
    },
    {
        "cinema": "Cinéma Rif",
        "name": "Grande Salle",
        "screen_type": "standard",
        "rows": 16,
        "seats_per_row": 20,
        "aisle_after": [4, 16],
        "broken_seats": [],
    },
    {
        "cinema": "Megarama Marrakech",
        "name": "Salle 1",
        "screen_type": "standard",
        "rows": 11,
        "seats_per_row": 16,
        "aisle_after": [2, 14],
        "broken_seats": [],
    },
    {
        "cinema": "Cinéma Le Colisée",
        "name": "Salle Unique",
        "screen_type": "premium",
        "rows": 12,
        "seats_per_row": 15,
        "aisle_after": [3, 12],
        "broken_seats": [],
    },
]

MOVIES = [
    {
        "slug": "inception",
        "title": "Inception",
        "original_title": "Inception",
        "release_year": 2010,
        "director": "Christopher Nolan",
        "cast": ["Leonardo DiCaprio", "Joseph Gordon-Levitt", "Elliot Page"],
        "genres": ["Sci-Fi", "Thriller", "Action"],
        "moods": ["cerebral", "mind-bending", "intense"],
        "synopsis": (
            "A thief who steals corporate secrets through dream-sharing technology is offered a chance "
            "to erase his criminal record, if he can pull off the impossible: planting an idea in a "
            "target's mind."
        ),
        "duration_minutes": 148,
        "rating": 8.4,
        "age_rating": "12+",
        "language": "English",
        "country": "United States",
        "poster_path": "/9gk7adHYeDvHkCSEqAvQNLV5Uge.jpg",
    },
    {
        "slug": "interstellar",
        "title": "Interstellar",
        "original_title": "Interstellar",
        "release_year": 2014,
        "director": "Christopher Nolan",
        "cast": ["Matthew McConaughey", "Anne Hathaway", "Jessica Chastain"],
        "genres": ["Sci-Fi", "Drama", "Adventure"],
        "moods": ["epic", "emotional", "cerebral"],
        "synopsis": (
            "With Earth becoming uninhabitable, a former pilot leads a mission through a wormhole "
            "near Saturn to find humanity a new home, while his daughter grows up without him."
        ),
        "duration_minutes": 169,
        "rating": 8.7,
        "age_rating": "12+",
        "language": "English",
        "country": "United States",
        "poster_path": "/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg",
    },
    {
        "slug": "the-dark-knight",
        "title": "The Dark Knight",
        "original_title": "The Dark Knight",
        "release_year": 2008,
        "director": "Christopher Nolan",
        "cast": ["Christian Bale", "Heath Ledger", "Aaron Eckhart"],
        "genres": ["Action", "Crime", "Drama"],
        "moods": ["dark", "intense", "epic"],
        "synopsis": (
            "Batman, Lieutenant Gordon and district attorney Harvey Dent take on the Joker, a criminal "
            "mastermind who pushes Gotham and its heroes to their moral limits."
        ),
        "duration_minutes": 152,
        "rating": 9.0,
        "age_rating": "12+",
        "language": "English",
        "country": "United States",
        "poster_path": "/qJ2tW6WMUDux911r6m7haRef0WH.jpg",
    },
    {
        "slug": "oppenheimer",
        "title": "Oppenheimer",
        "original_title": "Oppenheimer",
        "release_year": 2023,
        "director": "Christopher Nolan",
        "cast": ["Cillian Murphy", "Emily Blunt", "Robert Downey Jr."],
        "genres": ["Drama", "History", "Thriller"],
        "moods": ["intense", "cerebral", "dark"],
        "synopsis": (
            "The story of J. Robert Oppenheimer, the physicist who led the Manhattan Project and then "
            "faced the political consequences of the weapon he helped create."
        ),
        "duration_minutes": 181,
        "rating": 8.3,
        "age_rating": "12+",
        "language": "English",
        "country": "United States",
        "poster_path": "/8Gxv8gSFCU0XGDykEGv7zR1n2ua.jpg",
    },
    {
        "slug": "dune-part-two",
        "title": "Dune: Part Two",
        "original_title": "Dune: Part Two",
        "release_year": 2024,
        "director": "Denis Villeneuve",
        "cast": ["Timothée Chalamet", "Zendaya", "Rebecca Ferguson"],
        "genres": ["Sci-Fi", "Adventure", "Action"],
        "moods": ["epic", "immersive", "dark"],
        "synopsis": (
            "Paul Atreides unites with the Fremen to take revenge on the conspirators who destroyed his "
            "family, while trying to prevent the terrible future he keeps foreseeing."
        ),
        "duration_minutes": 166,
        "rating": 8.5,
        "age_rating": "12+",
        "language": "English",
        "country": "United States",
        "poster_path": "/1pdfLvkbY9ohJlCjQH2CZjjYVvJ.jpg",
    },
    {
        "slug": "blade-runner-2049",
        "title": "Blade Runner 2049",
        "original_title": "Blade Runner 2049",
        "release_year": 2017,
        "director": "Denis Villeneuve",
        "cast": ["Ryan Gosling", "Harrison Ford", "Ana de Armas"],
        "genres": ["Sci-Fi", "Drama", "Mystery"],
        "moods": ["cerebral", "melancholic", "slow-burn"],
        "synopsis": (
            "A young blade runner uncovers a secret that could break what remains of society, and goes "
            "looking for a man who disappeared thirty years earlier."
        ),
        "duration_minutes": 164,
        "rating": 8.0,
        "age_rating": "16+",
        "language": "English",
        "country": "United States",
        "poster_path": "/gajva2L0rPYkEWjzgFlBXCAVBE5.jpg",
    },
    {
        "slug": "parasite",
        "title": "Parasite",
        "original_title": "기생충",
        "release_year": 2019,
        "director": "Bong Joon-ho",
        "cast": ["Song Kang-ho", "Lee Sun-kyun", "Cho Yeo-jeong"],
        "genres": ["Thriller", "Drama", "Comedy"],
        "moods": ["tense", "dark", "thought-provoking"],
        "synopsis": (
            "A poor family slowly infiltrates the household of a wealthy Seoul couple, until an unexpected "
            "discovery turns the arrangement into a nightmare."
        ),
        "duration_minutes": 132,
        "rating": 8.5,
        "age_rating": "16+",
        "language": "Korean",
        "country": "South Korea",
        "poster_path": "/7IiTTgloJzvGI1TAYymCfbfl3vT.jpg",
    },
    {
        "slug": "la-la-land",
        "title": "La La Land",
        "original_title": "La La Land",
        "release_year": 2016,
        "director": "Damien Chazelle",
        "cast": ["Ryan Gosling", "Emma Stone", "John Legend"],
        "genres": ["Romance", "Musical", "Drama"],
        "moods": ["romantic", "bittersweet", "joyful"],
        "synopsis": (
            "A jazz pianist and an aspiring actress fall in love in Los Angeles while chasing careers that "
            "keep pulling them in different directions."
        ),
        "duration_minutes": 128,
        "rating": 8.0,
        "age_rating": "All ages",
        "language": "English",
        "country": "United States",
        "poster_path": "/uDO8zWDhfWwoFdKS4fzkUJt0Rf0.jpg",
    },
    {
        "slug": "whiplash",
        "title": "Whiplash",
        "original_title": "Whiplash",
        "release_year": 2014,
        "director": "Damien Chazelle",
        "cast": ["Miles Teller", "J.K. Simmons", "Melissa Benoist"],
        "genres": ["Drama", "Music"],
        "moods": ["intense", "inspiring", "tense"],
        "synopsis": (
            "A young jazz drummer is pushed to his absolute limit by a ruthless conservatory teacher who "
            "believes greatness is forged through pain."
        ),
        "duration_minutes": 106,
        "rating": 8.5,
        "age_rating": "12+",
        "language": "English",
        "country": "United States",
        "poster_path": "/7fn624j5lj3xTme2SgiLCeuedmO.jpg",
    },
    {
        "slug": "spirited-away",
        "title": "Spirited Away",
        "original_title": "千と千尋の神隠し",
        "release_year": 2001,
        "director": "Hayao Miyazaki",
        "cast": ["Rumi Hiiragi", "Miyu Irino", "Mari Natsuki"],
        "genres": ["Animation", "Fantasy", "Adventure"],
        "moods": ["whimsical", "magical", "family"],
        "synopsis": (
            "A ten-year-old girl wanders into a world of spirits and must work in a bathhouse for the gods "
            "to free her parents, who have been turned into pigs."
        ),
        "duration_minutes": 125,
        "rating": 8.6,
        "age_rating": "All ages",
        "language": "Japanese",
        "country": "Japan",
        "poster_path": "/39wmItIWsg5sZMyRUHLkWBcuVCM.jpg",
    },
    {
        "slug": "your-name",
        "title": "Your Name",
        "original_title": "君の名は。",
        "release_year": 2016,
        "director": "Makoto Shinkai",
        "cast": ["Ryunosuke Kamiki", "Mone Kamishiraishi"],
        "genres": ["Animation", "Romance", "Fantasy"],
        "moods": ["romantic", "magical", "emotional"],
        "synopsis": (
            "Two teenagers who have never met begin swapping bodies in their dreams, and set out to find "
            "each other before a coming catastrophe erases their connection."
        ),
        "duration_minutes": 106,
        "rating": 8.4,
        "age_rating": "All ages",
        "language": "Japanese",
        "country": "Japan",
        "poster_path": "/q719jXXEzOoYaps6babgKnONONX.jpg",
    },
    {
        "slug": "the-grand-budapest-hotel",
        "title": "The Grand Budapest Hotel",
        "original_title": "The Grand Budapest Hotel",
        "release_year": 2014,
        "director": "Wes Anderson",
        "cast": ["Ralph Fiennes", "Tony Revolori", "Saoirse Ronan"],
        "genres": ["Comedy", "Adventure", "Drama"],
        "moods": ["whimsical", "light", "stylish"],
        "synopsis": (
            "A legendary concierge and his loyal lobby boy get tangled in the theft of a priceless painting "
            "and a family inheritance in a fictional pre-war republic."
        ),
        "duration_minutes": 99,
        "rating": 8.1,
        "age_rating": "12+",
        "language": "English",
        "country": "United States",
        "poster_path": "/eWdyYQreja6JGCzqHWXpWHDrrPo.jpg",
    },
    {
        "slug": "everything-everywhere-all-at-once",
        "title": "Everything Everywhere All at Once",
        "original_title": "Everything Everywhere All at Once",
        "release_year": 2022,
        "director": "Daniel Kwan, Daniel Scheinert",
        "cast": ["Michelle Yeoh", "Ke Huy Quan", "Jamie Lee Curtis"],
        "genres": ["Sci-Fi", "Comedy", "Action"],
        "moods": ["mind-bending", "heartfelt", "chaotic"],
        "synopsis": (
            "A tired laundromat owner discovers she must connect with versions of herself across the "
            "multiverse to stop a nihilistic threat, and to reconnect with her daughter."
        ),
        "duration_minutes": 139,
        "rating": 8.0,
        "age_rating": "16+",
        "language": "English",
        "country": "United States",
        "poster_path": "/w3LxiVYdWWRvEVdn5RYq6jIqkb1.jpg",
    },
    {
        "slug": "the-godfather",
        "title": "The Godfather",
        "original_title": "The Godfather",
        "release_year": 1972,
        "director": "Francis Ford Coppola",
        "cast": ["Marlon Brando", "Al Pacino", "James Caan"],
        "genres": ["Crime", "Drama"],
        "moods": ["dark", "epic", "classic"],
        "synopsis": (
            "The ageing patriarch of a New York crime family hands control to his reluctant youngest son, "
            "who is drawn deeper into the business he once wanted to escape."
        ),
        "duration_minutes": 175,
        "rating": 9.2,
        "age_rating": "16+",
        "language": "English",
        "country": "United States",
        "poster_path": "/3bhkrj58Vtu7enYsRolD1fZdja1.jpg",
    },
    {
        "slug": "mad-max-fury-road",
        "title": "Mad Max: Fury Road",
        "original_title": "Mad Max: Fury Road",
        "release_year": 2015,
        "director": "George Miller",
        "cast": ["Tom Hardy", "Charlize Theron", "Nicholas Hoult"],
        "genres": ["Action", "Adventure", "Sci-Fi"],
        "moods": ["adrenaline", "intense", "epic"],
        "synopsis": (
            "In a desert wasteland, Max joins Furiosa and a group of escaping women in a relentless chase "
            "across the Fury Road to escape a warlord's army."
        ),
        "duration_minutes": 120,
        "rating": 8.1,
        "age_rating": "16+",
        "language": "English",
        "country": "Australia",
        "poster_path": "/8tZYtuWezp8JbcsvHYO0O46tFbo.jpg",
    },
    {
        "slug": "get-out",
        "title": "Get Out",
        "original_title": "Get Out",
        "release_year": 2017,
        "director": "Jordan Peele",
        "cast": ["Daniel Kaluuya", "Allison Williams", "Bradley Whitford"],
        "genres": ["Horror", "Thriller", "Mystery"],
        "moods": ["tense", "thought-provoking", "dark"],
        "synopsis": (
            "A young Black photographer visits his white girlfriend's family estate and slowly realises "
            "that something deeply sinister is happening behind their hospitality."
        ),
        "duration_minutes": 104,
        "rating": 7.7,
        "age_rating": "16+",
        "language": "English",
        "country": "United States",
        "poster_path": "/tFXcEccSQMf3lfhfXKSU9iRBpa3.jpg",
    },
    {
        "slug": "the-shawshank-redemption",
        "title": "The Shawshank Redemption",
        "original_title": "The Shawshank Redemption",
        "release_year": 1994,
        "director": "Frank Darabont",
        "cast": ["Tim Robbins", "Morgan Freeman", "Bob Gunton"],
        "genres": ["Drama"],
        "moods": ["inspiring", "emotional", "hopeful"],
        "synopsis": (
            "A banker sentenced to life in Shawshank prison builds an unlikely friendship with a fellow "
            "inmate and holds on to hope across two decades of injustice."
        ),
        "duration_minutes": 142,
        "rating": 9.3,
        "age_rating": "16+",
        "language": "English",
        "country": "United States",
        "poster_path": "/q6y0Go1tsGEsmtFryDOJo3dEmqu.jpg",
    },
    {
        "slug": "spider-man-across-the-spider-verse",
        "title": "Spider-Man: Across the Spider-Verse",
        "original_title": "Spider-Man: Across the Spider-Verse",
        "release_year": 2023,
        "director": "Joaquim Dos Santos, Kemp Powers, Justin K. Thompson",
        "cast": ["Shameik Moore", "Hailee Steinfeld", "Oscar Isaac"],
        "genres": ["Animation", "Action", "Adventure"],
        "moods": ["joyful", "epic", "stylish"],
        "synopsis": (
            "Miles Morales is thrown across the multiverse and clashes with the Spider Society over how "
            "a hero is allowed to save the people he loves."
        ),
        "duration_minutes": 140,
        "rating": 8.6,
        "age_rating": "All ages",
        "language": "English",
        "country": "United States",
        "poster_path": "/8Vt6mWEReuy4Of61Lnj5Xj704m8.jpg",
    },
    {
        "slug": "top-gun-maverick",
        "title": "Top Gun: Maverick",
        "original_title": "Top Gun: Maverick",
        "release_year": 2022,
        "director": "Joseph Kosinski",
        "cast": ["Tom Cruise", "Miles Teller", "Jennifer Connelly"],
        "genres": ["Action", "Drama"],
        "moods": ["adrenaline", "uplifting", "epic"],
        "synopsis": (
            "After thirty years as a test pilot, Maverick returns to train an elite group of graduates for "
            "a mission that demands everything he knows about flying."
        ),
        "duration_minutes": 130,
        "rating": 8.2,
        "age_rating": "12+",
        "language": "English",
        "country": "United States",
        "poster_path": "/62HCnUTziyWcpDaBO2i1DX17ljH.jpg",
    },
    {
        "slug": "knives-out",
        "title": "Knives Out",
        "original_title": "Knives Out",
        "release_year": 2019,
        "director": "Rian Johnson",
        "cast": ["Daniel Craig", "Ana de Armas", "Chris Evans"],
        "genres": ["Comedy", "Crime", "Mystery"],
        "moods": ["fun", "witty", "light"],
        "synopsis": (
            "A detective with a taste for theatrics investigates the death of a wealthy crime novelist, "
            "and every member of the eccentric family has a reason to lie."
        ),
        "duration_minutes": 130,
        "rating": 7.9,
        "age_rating": "12+",
        "language": "English",
        "country": "United States",
        "poster_path": "/pThyQovXQrw2m0s9x82twj48Jq4.jpg",
    },
    {
        "slug": "coco",
        "title": "Coco",
        "original_title": "Coco",
        "release_year": 2017,
        "director": "Lee Unkrich",
        "cast": ["Anthony Gonzalez", "Gael García Bernal", "Benjamin Bratt"],
        "genres": ["Animation", "Family", "Music"],
        "moods": ["emotional", "joyful", "family"],
        "synopsis": (
            "A boy who dreams of becoming a musician is transported to the Land of the Dead, where he "
            "uncovers the truth about his family's ban on music."
        ),
        "duration_minutes": 105,
        "rating": 8.4,
        "age_rating": "All ages",
        "language": "English",
        "country": "United States",
        "poster_path": "/gGEsBPAijhVUFoiNpgZXqRVWJt2.jpg",
    },
    {
        "slug": "the-matrix",
        "title": "The Matrix",
        "original_title": "The Matrix",
        "release_year": 1999,
        "director": "Lana Wachowski, Lilly Wachowski",
        "cast": ["Keanu Reeves", "Laurence Fishburne", "Carrie-Anne Moss"],
        "genres": ["Sci-Fi", "Action"],
        "moods": ["mind-bending", "intense", "classic"],
        "synopsis": (
            "A hacker learns that the world he knows is a simulation built to pacify humanity, and joins a "
            "resistance fighting the machines that control it."
        ),
        "duration_minutes": 136,
        "rating": 8.7,
        "age_rating": "16+",
        "language": "English",
        "country": "United States",
        "poster_path": "/f89U3ADr1oiB1s9GkdPOEpXUk5H.jpg",
    },
    {
        "slug": "barbie",
        "title": "Barbie",
        "original_title": "Barbie",
        "release_year": 2023,
        "director": "Greta Gerwig",
        "cast": ["Margot Robbie", "Ryan Gosling", "America Ferrera"],
        "genres": ["Comedy", "Fantasy", "Adventure"],
        "moods": ["fun", "stylish", "light"],
        "synopsis": (
            "Barbie leaves the pastel perfection of Barbieland for the real world, where she and Ken "
            "discover what it actually means to be human."
        ),
        "duration_minutes": 114,
        "rating": 6.8,
        "age_rating": "12+",
        "language": "English",
        "country": "United States",
        "poster_path": "/iuFNMS8U5cb6xfzi51Dbkovj7vM.jpg",
    },
    {
        "slug": "john-wick-chapter-4",
        "title": "John Wick: Chapter 4",
        "original_title": "John Wick: Chapter 4",
        "release_year": 2023,
        "director": "Chad Stahelski",
        "cast": ["Keanu Reeves", "Donnie Yen", "Bill Skarsgård"],
        "genres": ["Action", "Thriller"],
        "moods": ["adrenaline", "intense", "dark"],
        "synopsis": (
            "John Wick takes his fight against the High Table global, hunting down the elders who put a "
            "price on his head while old allies become enemies."
        ),
        "duration_minutes": 169,
        "rating": 7.7,
        "age_rating": "16+",
        "language": "English",
        "country": "United States",
        "poster_path": "/vZloFAK7NmvMGKE7VkF5UHaz0I.jpg",
    },
    {
        "slug": "amelie",
        "title": "Amélie",
        "original_title": "Le Fabuleux Destin d'Amélie Poulain",
        "release_year": 2001,
        "director": "Jean-Pierre Jeunet",
        "cast": ["Audrey Tautou", "Mathieu Kassovitz", "Rufus"],
        "genres": ["Romance", "Comedy"],
        "moods": ["whimsical", "romantic", "feel-good"],
        "synopsis": (
            "A shy Montmartre waitress decides to secretly improve the lives of the people around her, "
            "until she has to find the courage to change her own."
        ),
        "duration_minutes": 122,
        "rating": 8.3,
        "age_rating": "All ages",
        "language": "French",
        "country": "France",
        "poster_path": None,
    },
    {
        "slug": "les-chevaux-de-dieu",
        "title": "Les Chevaux de Dieu",
        "original_title": "Les Chevaux de Dieu",
        "release_year": 2012,
        "director": "Nabil Ayouch",
        "cast": ["Abdelhakim Rachid", "Abdelilah Rachid", "Hamza Souidek"],
        "genres": ["Drama"],
        "moods": ["intense", "thought-provoking", "gritty"],
        "synopsis": (
            "Two brothers growing up in a poor Casablanca neighbourhood drift from petty crime toward "
            "extremism, tracing how ordinary lives can end in the 2003 attacks."
        ),
        "duration_minutes": 117,
        "rating": 7.3,
        "age_rating": "16+",
        "language": "Arabic",
        "country": "Morocco",
        "poster_path": None,
    },
    {
        "slug": "ali-zaoua",
        "title": "Ali Zaoua: Prince of the Streets",
        "original_title": "علي زاوا",
        "release_year": 2000,
        "director": "Nabil Ayouch",
        "cast": ["Mounïm Kbab", "Mustapha Hansali", "Hicham Moussoune"],
        "genres": ["Drama"],
        "moods": ["emotional", "gritty", "heartfelt"],
        "synopsis": (
            "A group of street children in Casablanca set out to give their murdered friend the burial he "
            "dreamed of, as a sailor on an island of his own."
        ),
        "duration_minutes": 99,
        "rating": 7.9,
        "age_rating": "12+",
        "language": "Arabic",
        "country": "Morocco",
        "poster_path": None,
    },
    {
        "slug": "casanegra",
        "title": "Casanegra",
        "original_title": "كازانيكرا",
        "release_year": 2008,
        "director": "Nour-Eddine Lakhmari",
        "cast": ["Anas El Baz", "Omar Lotfi", "Ghita Nor"],
        "genres": ["Drama", "Crime"],
        "moods": ["gritty", "dark", "intense"],
        "synopsis": (
            "Two friends in Casablanca, tired of scraping by, take one last job that they hope will buy "
            "them a way out of the city and into a better life."
        ),
        "duration_minutes": 131,
        "rating": 7.4,
        "age_rating": "16+",
        "language": "Arabic",
        "country": "Morocco",
        "poster_path": None,
    },
]

# Local wall-clock start times used by the seed showtime generator.
SHOWTIME_SLOTS = [(11, 30), (15, 30), (19, 30), (23, 30)]

# Ticket price per seat, in cents, by hall screen type.
PRICES_BY_SCREEN_TYPE = {
    "standard": 5000,
    "premium": 8000,
    "imax": 9000,
    "vip": 13000,
}

FORMAT_BY_SCREEN_TYPE = {
    "standard": "2D",
    "premium": "2D",
    "imax": "IMAX",
    "vip": "VIP",
}
