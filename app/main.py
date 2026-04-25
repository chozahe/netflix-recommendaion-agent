from app.config import settings


def main() -> None:
    print("Netflix Recommendation Agent started")
    print("Multi-agent config:")
    print(f"- Analyst model: {settings.analyst_model}")
    print(f"- Search model: {settings.search_model}")
    print(f"- Finalizer model: {settings.finalizer_model}")
    print(f"Base URL: {settings.openai_base_url}")
    print("Project skeleton works")


if __name__ == "__main__":
    main()
