from pathlib import Path

from supabase import Client, create_client


def get_supabase_client(url: str, key: str) -> Client | None:
    if not url or not key:
        return None
    return create_client(url, key)


def upload_file(
    client: Client | None, bucket: str, object_key: str, local_path: str
) -> bool:
    if client is None:
        return False
    file_bytes = Path(local_path).read_bytes()
    client.storage.from_(bucket).upload(
        path=object_key,
        file=file_bytes,
        file_options={"content-type": "application/json", "upsert": "true"},
    )
    return True
