from __future__ import annotations

import logging

from google.cloud import storage
from google.cloud.exceptions import NotFound

from src.config import GCP_PROJECT, GCS_BUCKET

logger = logging.getLogger(__name__)

_storage_client = storage.Client(project=GCP_PROJECT)


class ImageStorageError(Exception):
    """Raised when the underlying image storage backend fails unexpectedly."""


class GcsImageRepository:
    """Fetches fingerprint images directly from the GCS bucket the back writes to.

    Object-key convention: media/investigation-case/{caseId}/{folder}/{id}.*
    (same as the back's ImageStoragePort, cf. ADR-0002/0003).
    """

    def __init__(self, bucket: storage.Bucket) -> None:
        self._bucket = bucket

    def fetch(self, case_id: str, folder: str, image_id: str) -> tuple[str, bytes] | None:
        """Return (filename, bytes), or None if the object is missing."""
        # The back stores the original file extension verbatim (".JPG", ".png", ...)
        # and GCS object keys are case-sensitive: resolve the object by listing
        # on the "{id}." prefix instead of guessing from a fixed extension list.
        prefix = f"media/investigation-case/{case_id}/{folder}/{image_id}."

        try:
            blob = next(iter(self._bucket.list_blobs(prefix=prefix, max_results=1)), None)
            if blob is not None:
                filename = blob.name.rsplit("/", 1)[-1]
                return (filename, blob.download_as_bytes())
        except NotFound:
            pass
        except Exception as exc:
            raise ImageStorageError(f"Failed to fetch image {image_id} from case {case_id}/{folder}") from exc

        logger.warning("Image %s not found in case %s/%s, skipping it", image_id, case_id, folder)
        return None


def get_image_repository() -> GcsImageRepository:
    return GcsImageRepository(_storage_client.bucket(GCS_BUCKET))
