from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, List, Sequence
from urllib.parse import urlunparse

from event_model import (
    ComposeStreamResource,
    ComposeStreamResourceBundle,
    StreamDatum,
    StreamResource,
)


@dataclass
class HDFDataset:
    data_key: str
    dataset: str
    shape: Sequence[int] = field(default_factory=tuple)
    dtype_numpy: str = ""
    multiplier: int = 1
    swmr: bool = False
    # Represents number of points/frames in first chunking dimension.
    # If 0 or None, assume all points in single chunk.
    # Otherwise, assume equally sized chunks of chunk_size points/frames,
    # except potentially last chunk which may be smaller.
    chunk_size: int | None = None


SLICE_NAME = "AD_HDF5_SWMR_SLICE"


class HDFFile:
    """
    :param full_file_name: Absolute path to the file to be written
    :param datasets: Datasets to write into the file
    """

    def __init__(
        self,
        full_file_name: Path,
        datasets: List[HDFDataset],
        hostname: str = "localhost",
    ) -> None:
        self._last_emitted = 0
        self._hostname = hostname

        if len(datasets) == 0:
            self._bundles = []
            return None

        bundler_composer = ComposeStreamResource()

        uri = urlunparse(
            (
                "file",
                self._hostname,
                str(full_file_name.absolute()),
                "",
                "",
                None,
            )
        )

        self._bundles: List[ComposeStreamResourceBundle] = [
            bundler_composer(
                mimetype="application/x-hdf5",
                uri=uri,
                data_key=ds.data_key,
                parameters={
                    "dataset": ds.dataset,
                    "swmr": ds.swmr,
                    "multiplier": ds.multiplier,
                    "chunk_size": ds.chunk_size,
                },
                uid=None,
                validate=True,
            )
            for ds in datasets
        ]

    def stream_resources(self) -> Iterator[StreamResource]:
        for bundle in self._bundles:
            yield bundle.stream_resource_doc

    def stream_data(self, indices_written: int) -> Iterator[StreamDatum]:
        # Indices are relative to resource
        if indices_written > self._last_emitted:
            indices = {
                "start": self._last_emitted,
                "stop": indices_written,
            }
            self._last_emitted = indices_written
            for bundle in self._bundles:
                yield bundle.compose_stream_datum(indices)
        return None

    def close(self) -> None:
        for bundle in self._bundles:
            bundle.close()
