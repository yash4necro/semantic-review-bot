import os
from groq import Groq
from dotenv import load_dotenv
from retriever import retrieve, format_context

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """You are a senior software engineer performing a code review.
You will be given a code diff and optionally some similar code from the existing 
codebase for context.

Your review should cover:
- Correctness: does the logic look right?
- Consistency: does it follow patterns already in the codebase?
- Edge cases: what could go wrong?
- Readability: is it clear what this code does?

Be direct and specific. Reference actual lines or function names when you can.
If the similar code context is relevant, use it — if it isn't, ignore it.
Keep the review under 400 words."""


def review(diff: str) -> None:
    """
    Given a code diff string, retrieve similar codebase context
    and stream a code review from Groq.
    """
    print("\n🔍 Finding similar code in codebase...")
    matches = retrieve(diff, top_k=5)

    # Show what context we're injecting
    relevant = [m for m in matches if m["distance"] < 0.7]
    if relevant:
        print(f"📎 Injecting {len(relevant)} similar function(s) as context:")
        for m in relevant:
            print(f"   [{m['distance']}] {m['filepath']} → {m['name']}()")
    else:
        print("📎 No closely similar code found — reviewing without context")

    context = format_context(matches)

    user_message = f"""## Code to review

{diff}

## Similar code from the codebase (for context)

{context}
"""

    print("\n" + "=" * 60)
    print("📝 CODE REVIEW")
    print("=" * 60 + "\n")

    # Stream the response — don't wait for the full reply
    with client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_message}
        ],
        max_tokens=600,
        stream=True
    ) as stream:
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                print(delta, end="", flush=True)

    print("\n")


if __name__ == "__main__":
    # Test with a realistic Flask-style diff
    test_diff = '''
def register_user(username, password):
    user = User(username=username, password=password)
    db.session.add(user)
    db.session.commit()
    return user
'''
    review(test_diff)