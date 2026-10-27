"""CLI wrapper for generating the synthetic retail database and CSV files."""

from app.core.config import get_settings
from app.data.retail import export_csv, seed_database


def main() -> None:
    settings = get_settings()
    path = seed_database(settings.database_file)
    export_csv(settings.database_file.parents[1] / "data" / "synthetic_retail")
    print(f"Seeded synthetic retail database at {path}")


if __name__ == "__main__":
    main()
