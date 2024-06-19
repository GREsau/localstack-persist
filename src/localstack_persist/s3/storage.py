import base64
import hashlib
import os
import re
import shutil
from threading import Lock
from localstack.aws.api.s3 import BucketName, MultipartUploadId, PartNumber
from localstack.services.s3.constants import S3_CHUNK_SIZE
from localstack.services.s3.utils import ChecksumHash, ObjectRange, get_s3_checksum

# TODO update imports for localstack 3.5.1
from localstack.services.s3.v3.models import S3Multipart, S3Object, S3Part
from localstack.services.s3.v3.storage import (
    S3ObjectStore,
    S3StoredMultipart,
    S3StoredObject,
    LimitedStream,
)
from localstack.utils.files import mkdir, rm_rf
from typing import IO, BinaryIO, Iterator, Literal, Optional
from ..config import BASE_DIR

special_chars = re.compile(r"[\x00-\x1f\x7f\\/\":*?|<>$%]")


def encode_file_name_char(match: re.Match):
    char = match.group(0)
    return f"%{ord(char):x}"


def encode_file_name(name: str) -> str:
    return special_chars.sub(encode_file_name_char, name)


class PersistedS3StoredObject(S3StoredObject):
    _file: BinaryIO
    _size: Optional[int]
    _md5: "hashlib._Hash"
    _etag: Optional[str]
    _checksum: Optional[ChecksumHash]
    _checksum_value: Optional[str]

    def __init__(
        self,
        s3_object: S3Object | S3Part,
        store: "PersistedS3ObjectStore",
        file: BinaryIO,
        mode: Literal["r", "w"],
    ):
        super().__init__(s3_object, mode)
        self._store = store
        self._file = file
        self._size = None
        self._md5 = hashlib.md5(usedforsecurity=False)
        self._etag = None
        self._checksum = (
            get_s3_checksum(s3_object.checksum_algorithm)
            if s3_object.checksum_algorithm
            else None
        )
        self._checksum_value = None

    def close(self):
        self._store.close_file(self._file)
        self.closed = True

    def truncate(self, size: Optional[int] = None) -> int:
        return self._file.truncate(size)

    def write(self, s: Optional[IO[bytes] | S3StoredObject | LimitedStream]) -> int:
        self._file.truncate()

        if s:
            while data := s.read(S3_CHUNK_SIZE):
                self._file.write(data)
                self._md5.update(data)
                if self._checksum:
                    self._checksum.update(data)

        self._etag = self.s3_object.etag = self._md5.hexdigest()
        if self._checksum:
            self._checksum_value = base64.b64encode(self._checksum.digest()).decode()
        self._size = self.s3_object.size = self._file.tell()

        self._file.seek(0)

        return self._size

    def append(self, part: IO[bytes] | S3StoredObject) -> int:
        read = 0
        while data := part.read(S3_CHUNK_SIZE):
            self._file.write(data)
            self._md5.update(data)
            if self._checksum:
                self._checksum.update(data)
            read += len(data)

        self._etag = self.s3_object.etag = self._md5.hexdigest()
        if self._checksum:
            self._checksum_value = base64.b64encode(self._checksum.digest()).decode()
        self._size = self.s3_object.size = (self._size or 0) + read

        return read

    def read(self, s: int = -1) -> bytes:
        return self._file.read(s)

    def seek(self, offset: int, whence: int = 0) -> int:
        return self._file.seek(offset, whence)

    @property
    def checksum(self) -> Optional[str]:
        if self._checksum_value is None and self._checksum:
            self._compute_hashes()

        return self._checksum_value

    @property
    def etag(self) -> str:
        if self._etag is None:
            self._compute_hashes()
            assert self._etag is not None

        return self._etag

    @property
    def last_modified(self) -> int:
        return os.stat(self._file.fileno()).st_mtime_ns

    def __iter__(self) -> Iterator[bytes]:
        while data := self.read(S3_CHUNK_SIZE):
            yield data

    def __del__(self):
        self.close()

    def _compute_hashes(self):
        while data := self.read(S3_CHUNK_SIZE):
            self._md5.update(data)
            if self._checksum:
                self._checksum.update(data)

        self._etag = self.s3_object.etag = self._md5.hexdigest()
        if self._checksum:
            self._checksum_value = base64.b64encode(self._checksum.digest()).decode()
        self._size = self.s3_object.size = self._file.tell()

        self._file.seek(0)


class PersistedS3StoredMultipart(S3StoredMultipart):
    _s3_store: (  # pyright: ignore [reportIncompatibleVariableOverride]
        "PersistedS3ObjectStore"
    )
    _dir: str
    # Hide unused attribute from base class
    parts: None  # pyright: ignore [reportIncompatibleVariableOverride]

    def __init__(
        self,
        s3_store: "PersistedS3ObjectStore",
        bucket: BucketName,
        s3_multipart: S3Multipart,
    ):
        super().__init__(s3_store, bucket, s3_multipart)
        self._dir = s3_store._multipart_path(bucket, s3_multipart.id)
        mkdir(self._dir)

    def open(
        self, s3_part: S3Part, mode: Literal["r", "w"] = "r"
    ) -> PersistedS3StoredObject:
        path = os.path.join(self._dir, f"part-{s3_part.part_number}")
        file = self._s3_store.open_file(path, mode)
        return PersistedS3StoredObject(s3_part, self._s3_store, file, mode)

    def remove_part(self, s3_part: S3Part):
        path = os.path.join(self._dir, f"part-{s3_part.part_number}")
        os.unlink(path)

    def complete_multipart(self, parts: list[PartNumber] | list[S3Part]) -> None:
        s3_stored_object = self._s3_store.open(
            self.bucket, self.s3_multipart.object, "w"
        )
        s3_stored_object.truncate()

        for s3_part in parts:
            part_number = s3_part if isinstance(s3_part, int) else s3_part.part_number
            path = os.path.join(self._dir, f"part-{part_number}")
            with open(path, "rb") as file:
                s3_stored_object.append(file)

        s3_stored_object.seek(0)

    def close(self):
        pass

    def copy_from_object(
        self,
        s3_part: S3Part,
        src_bucket: BucketName,
        src_s3_object: S3Object,
        range_data: Optional[ObjectRange],
    ) -> None:
        with self._s3_store.open(src_bucket, src_s3_object, "r") as src_stored_object:
            with self.open(s3_part, "w") as stored_part:
                src_stream = (
                    LimitedStream(src_stored_object, range_data=range_data)
                    if range_data
                    else src_stored_object
                )
                stored_part.write(src_stream)


class PersistedS3ObjectStore(S3ObjectStore):
    root_directory = os.path.join(BASE_DIR, "s3", "assets")

    def __init__(self) -> None:
        super().__init__()
        self._open_files = set[BinaryIO]()
        self._open_files_lock = Lock()

    def open(
        self,
        bucket: BucketName,
        s3_object: S3Object,
        mode: Literal["r", "w"] = "r",
    ) -> PersistedS3StoredObject:
        path = self._object_path(bucket, s3_object)
        file = self.open_file(path, mode)
        return PersistedS3StoredObject(s3_object, self, file, mode)

    def remove(self, bucket: BucketName, s3_object: S3Object | list[S3Object]):
        s3_objects = s3_object if isinstance(s3_object, list) else [s3_object]

        for s3_object in s3_objects:
            path = self._object_path(bucket, s3_object)
            os.unlink(path)

    def copy(
        self,
        src_bucket: BucketName,
        src_object: S3Object,
        dest_bucket: BucketName,
        dest_object: S3Object,
    ) -> PersistedS3StoredObject:
        src_path = self._object_path(src_bucket, src_object)
        dest_path = self._object_path(dest_bucket, dest_object)
        if src_path != dest_path:
            shutil.copy(src_path, dest_path)

        return self.open(dest_bucket, dest_object, "r")

    def get_multipart(
        self, bucket: BucketName, upload_id: S3Multipart | MultipartUploadId
    ) -> PersistedS3StoredMultipart:
        # type annotations on base class are incorrect!
        assert isinstance(upload_id, S3Multipart)
        return PersistedS3StoredMultipart(self, bucket, upload_id)

    def remove_multipart(self, bucket: BucketName, s3_multipart: S3Multipart):
        rm_rf(self._multipart_path(bucket, s3_multipart.id))

    def create_bucket(self, bucket: BucketName):
        mkdir(self._bucket_path(bucket))

    def delete_bucket(self, bucket: BucketName):
        rm_rf(self._bucket_path(bucket))

    def open_file(self, path: str, mode: Literal["r", "w"]) -> BinaryIO:
        file = open(path, mode + "b")
        with self._open_files_lock:
            self._open_files.add(file)
        return file

    def close_file(self, file: BinaryIO):
        with self._open_files_lock:
            file.close()
            self._open_files.discard(file)

    def flush(self):
        with self._open_files_lock:
            for f in self._open_files:
                f.flush()

    def _bucket_path(self, bucket: BucketName) -> str:
        return os.path.join(self.root_directory, bucket)

    def _object_path(self, bucket: BucketName, s3_object: S3Object) -> str:
        key = f"{s3_object.key}@{s3_object.version_id or 'null'}"
        return os.path.join(self._bucket_path(bucket), encode_file_name(key))

    def _multipart_path(
        self,
        bucket: BucketName,
        upload_id: str,
    ) -> str:
        return os.path.join(self._bucket_path(bucket), "multiparts", upload_id)
