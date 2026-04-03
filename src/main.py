import sys
import argparse
from reviewer import review


def main():
    parser = argparse.ArgumentParser(
        description="Semantic Code Review Bot — LLM reviews enriched with codebase context"
    )

    parser.add_argument(
        "--diff",
        type=str,
        help="Path to a file to review"
    )

    args = parser.parse_args()

    if args.diff:
        # Review a specific file
        with open(args.diff, "r") as f:
            code = f.read()
        review(code)

    elif not sys.stdin.isatty():
        # Piped input — e.g. git diff HEAD~1 | python3 src/main.py
        code = sys.stdin.read()
        if code.strip():
            review(code)
        else:
            print("No input received.")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()