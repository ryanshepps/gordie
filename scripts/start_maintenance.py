"""Start the maintenance-mode server.

Use this in place of `scripts/start_server.py` when the hosted instance is
being migrated. The agent, DB, and scheduled jobs are NOT loaded.
"""

from dotenv import load_dotenv

load_dotenv()

from server.maintenance_server import main  # noqa: E402

if __name__ == "__main__":
    main()
