"""One-off: assign every unowned culture (owner_id IS NULL) to a user id.

Run once against prod after migration 0014 lands, before sharing the link
further — otherwise existing batches stay invisible (owner_id NULL never
matches a real caller's owner_id, per the routers' ownership filters) rather
than becoming someone else's.

Usage:
    FERMENTTRACK_DATABASE_URL=postgresql+psycopg://... \\
        python scripts/assign_existing_data_to_user.py <supabase-user-id>

Get <supabase-user-id> by signing into the deployed frontend once (it creates
an anonymous session) and reading auth.users.id from the Supabase table editor,
or the JWT's `sub` claim from the browser's network tab.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from fermenttrack.database import async_session_maker
from fermenttrack.models import Culture


async def main(owner_id: str) -> None:
    async with async_session_maker() as db:
        result = await db.execute(select(Culture).where(Culture.owner_id.is_(None)))
        cultures = list(result.scalars().all())
        for culture in cultures:
            culture.owner_id = owner_id
        await db.commit()
        print(f"Assigned {len(cultures)} culture(s) to {owner_id!r}.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(1)
    asyncio.run(main(sys.argv[1]))
