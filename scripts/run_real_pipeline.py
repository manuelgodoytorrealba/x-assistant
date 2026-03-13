import subprocess


def run(script_name: str):
    print(f"\n▶ Ejecutando {script_name}...\n")
    subprocess.run(["python", script_name], check=True)


def main():
    run("scripts/init_db.py")
    run("scripts/fetch_tweets.py")
    run("scripts/score_posts.py")
    run("scripts/generate_drafts.py")
    run("scripts/build_digest.py")


if __name__ == "__main__":
    main()