"""Generate traffic to demonstrate RAG performance incident.

Sends horror recommendation queries to the chat endpoint to trigger
RAG retrieval and expose the sequential scan performance degradation.

Usage:
    uv run python scripts/generate_incident_traffic.py
    uv run python scripts/generate_incident_traffic.py --base-url http://localhost:8000 --count 20
"""

import argparse
import statistics
import sys
import time

import httpx

# Queries classified as horror_recommendation → triggers RAG pipeline
QUERIES = [
    "Recommande-moi un bon film d'horreur avec des fantomes",
    "Je cherche un film de zombies vraiment effrayant",
    "Quel est le meilleur slasher des annees 80 ?",
    "Suggest a psychological horror movie",
    "Un film d'horreur pour Halloween, qu'est-ce que tu conseilles ?",
    "Parle-moi des films de vampires les plus terrifiants",
    "What are the scariest ghost movies ever made?",
    "Je veux un film d'horreur japonais, tu as des idees ?",
    "Quel film d'horreur a les meilleurs jump scares ?",
    "Recommande-moi un film de loup-garou",
    "Best cosmic horror movies like Lovecraft?",
    "Un bon film d'horreur recent a regarder ce soir",
    "Quels sont les classiques du cinema d'horreur ?",
    "Film d'horreur avec une maison hantee, des suggestions ?",
    "Tell me about scary movies with demons and exorcisms",
    "Je cherche un film d'horreur psychologique style Shining",
    "Quel film d'horreur me recommandes-tu pour ce weekend ?",
    "Un bon film de found footage, ca existe encore ?",
    "Recommande-moi un film d'horreur avec des enfants flippants",
    "Best horror anthology movies to watch?",
]

TEST_USER = {
    "username": "incident_test_user",
    "email": "incident_test@horrorbot.local",
    "password": "TestIncident2026!",
}


def register_user(client: httpx.Client, base_url: str) -> None:
    """Register test user (ignore 409 if already exists)."""
    resp = client.post(f"{base_url}/api/v1/auth/register", json=TEST_USER)
    if resp.status_code == 201:
        print(f"[+] Utilisateur '{TEST_USER['username']}' cree")
    elif resp.status_code == 409:
        print(f"[=] Utilisateur '{TEST_USER['username']}' existe deja")
    else:
        print(f"[!] Erreur inscription: {resp.status_code} — {resp.text}")
        sys.exit(1)


def get_token(client: httpx.Client, base_url: str) -> str:
    """Get JWT token for test user."""
    resp = client.post(
        f"{base_url}/api/v1/auth/token",
        json={
            "username": TEST_USER["username"],
            "password": TEST_USER["password"],
        },
    )
    if resp.status_code != 200:
        print(f"[!] Erreur authentification: {resp.status_code} — {resp.text}")
        sys.exit(1)
    token = resp.json()["access_token"]
    print(f"[+] Token JWT obtenu")
    return token


def send_chat(
    client: httpx.Client, base_url: str, token: str, message: str
) -> tuple[int, float]:
    """Send chat request, return (status_code, duration_ms)."""
    start = time.perf_counter()
    resp = client.post(
        f"{base_url}/api/v1/chat",
        json={"message": message},
        headers={"Authorization": f"Bearer {token}"},
        timeout=60.0,
    )
    duration_ms = (time.perf_counter() - start) * 1000
    return resp.status_code, duration_ms


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate incident traffic for HorrorBot")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--count", type=int, default=15, help="Number of requests")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests (s)")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  HorrorBot — Generateur de trafic incident")
    print(f"  URL: {args.base_url} | Requetes: {args.count}")
    print(f"{'='*60}\n")

    with httpx.Client() as client:
        register_user(client, args.base_url)
        token = get_token(client, args.base_url)

        durations: list[float] = []
        errors = 0

        print(f"\n--- Envoi de {args.count} requetes chat ---\n")
        for i in range(args.count):
            query = QUERIES[i % len(QUERIES)]
            status, duration_ms = send_chat(client, args.base_url, token, query)

            symbol = "+" if status == 200 else "!"
            print(f"  [{symbol}] {i+1:2d}/{args.count} | {status} | {duration_ms:7.0f}ms | {query[:50]}...")

            if status == 200:
                durations.append(duration_ms)
            else:
                errors += 1

            if i < args.count - 1:
                time.sleep(args.delay)

        # Summary
        print(f"\n{'='*60}")
        print(f"  RESUME")
        print(f"{'='*60}")
        print(f"  Requetes envoyees : {args.count}")
        print(f"  Succes            : {len(durations)}")
        print(f"  Erreurs           : {errors}")

        if durations:
            sorted_d = sorted(durations)
            p95_idx = int(len(sorted_d) * 0.95)
            p95 = sorted_d[min(p95_idx, len(sorted_d) - 1)]

            print(f"  Latence min       : {min(durations):7.0f}ms")
            print(f"  Latence max       : {max(durations):7.0f}ms")
            print(f"  Latence moyenne   : {statistics.mean(durations):7.0f}ms")
            print(f"  Latence mediane   : {statistics.median(durations):7.0f}ms")
            print(f"  Latence P95       : {p95:7.0f}ms")

            if p95 > 500:
                print(f"\n  [!!] ALERTE : P95 ({p95:.0f}ms) > 500ms — incident de performance detecte!")
            else:
                print(f"\n  [OK] P95 ({p95:.0f}ms) < 500ms — performance nominale")

        print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
