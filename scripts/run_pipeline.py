import argparse
import subprocess


def run(script_name: str, extra_args=None):
    extra_args = extra_args or []
    print(f"\n▶ Ejecutando {script_name}...\n")
    subprocess.run(["python", script_name, *extra_args], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["reply", "inspiration"],
        default="reply",
        help="Modo de ejecución del pipeline",
    )
    args = parser.parse_args()

    mode = args.mode

    run("scripts/init_db.py")
    run("scripts/reset_runtime_data.py")
    run("scripts/fetch_tweets.py", ["--mode", mode])
    run("scripts/score_posts.py", ["--mode", mode])
    run("scripts/generate_drafts.py", ["--mode", mode])
    run("scripts/build_digest.py", ["--mode", mode])


if __name__ == "__main__":
    main()
