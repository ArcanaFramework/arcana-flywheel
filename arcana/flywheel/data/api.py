"""
Flywheel api class
"""
from __future__ import annotations
import typing as ty
from pathlib import Path
import attrs
from fileformats.core import FileSet
from arcana.core.data.store import RemoteStore
from arcana.core.data.row import DataRow
from arcana.core.data.tree import DataTree
from arcana.core.data.entry import DataEntry

from arcana.common import Clinical

import flywheel

# from flywheel.models.project_input import ProjectInput

import logging

logger = logging.getLogger("arcana")


@attrs.define(kw_only=True, slots=False)
class Flywheel(RemoteStore):
    """
    Access class for Flywheel data repositores

    For a data management system/data structure to be compatible with Arcana, it must
    meet a number of criteria. In Arcana, a store is assumed to

        * contain multiple projects/datasets addressable by unique IDs.
        * organise data within each project/dataset in trees
        * store arbitrary numbers of data "items" (e.g. "file-sets" and fields) within
          each tree node (including non-leaf nodes) addressable by unique "paths" relative
          to the node.
        * allow derivative data to be stored within in separate namespaces for different
          analyses on the same data
    """

    # Uncomment if the remote store supports datasets with specific data space/hierarchy,
    # or have obvious defaults
    # DEFAULT_SPACE = Clinical
    # DEFAULT_HIERARCHY = ["subject", "timepoint"]

    #############################
    # DataStore abstractmethods #
    #############################

    def populate_tree(self, tree: DataTree):
        """Scans the data present in the dataset and populates the nodes of the data
        tree with those found in the dataset using the ``DataTree.add_leaf`` method for
        every "leaf" node of the dataset tree.

        The order that the tree leaves are added is important and should be consistent
        between reads, because it is used to give default values to the ID's of data
        space axes not explicitly in the hierarchy of the tree.

        Parameters
        ----------
        tree : DataTree
            the data tree to populate with leaf nodes
        """

        with self.connection:
            logger.debug(f"DATASET ID: {tree.dataset_id}")
            fwproject = self.connection.lookup(f"arcana_tests/{tree.dataset_id}")
            subjects = sorted(fwproject.subjects(), key=lambda x: x.label)
            for fwsubject in subjects:
                fwsessions = sorted(
                    fwsubject.sessions(),
                    key=lambda x: x.timestamp,
                )
                for fwsess in fwsessions:
                    date = fwsess.date.strftime("%Y%m%d") if fwsess.timestamp else None
                    metadata = {
                        "session": {
                            "date": date,
                            "age": fwsess.age / 31536000
                            if fwsess.age is not None
                            else -1,
                        }
                    }
                    tree.add_leaf([fwsubject.label, fwsess.label], metadata=metadata)

    def populate_row(self, row: DataRow):
        """Scans a node in the data tree corresponding to the data row and populates a
        row with all data entries found in the corresponding node in the data
        store (e.g. scans within an imaging session) using ``DataRow.add_entry``.
        Within a node/row there are assumed to be two types of entries, "primary"
        entries (e.g. acquired scans) common to all analyses performed on the dataset,
        and "derivative" entries corresponding to intermediate outputs
        of previously performed analyses. These types should be stored in separate
        namespaces so there is no chance of a derivative overriding a primary data item.

        The name of the dataset/analysis a derivative was generated by is appended to
        to a base path, delimited by "@", e.g. "brain_mask@my_analysis". The dataset
        name is left blank by default, in which case "@" is just appended to the
        derivative path, i.e. "brain_mask@".

        Parameters
        ----------
        row : DataRow
            The row to populate with entries
        """

        raise NotImplementedError

    def save_dataset_definition(
        self, dataset_id: str, definition: dict[str, ty.Any], name: str
    ):
        """Save definition of a dataset within the store

        Parameters
        ----------
        dataset_id: str
            The ID/path of the dataset within the store
        definition: dict[str, Any]
            A dictionary containing the definition of the dataset to be saved.
            The dictionary is in a format ready to be dumped to a JSON or
            YAML file
        name: str
            Name for the dataset definition to distinguish it from other
            definitions for the same directory/project"""
        raise NotImplementedError

    def load_dataset_definition(self, dataset_id: str, name: str) -> dict[str, ty.Any]:
        """Load definition of a dataset saved within the store

        Parameters
        ----------
        dataset_id: str
            The ID (e.g. file-system path, XNAT project ID) of the project
        name: str
            Name for the dataset definition to distinguish it from other
            definitions for the same directory/project

        Returns
        -------
        definition: dict[str, Any]
            A dictionary containing the dataset definition that was saved in the
            data store
        """
        raise NotImplementedError

    def connect(self):
        """
        If a connection session is required to the store it should be generated here

        Parameters
        ----------
        session : Any
            the session object returned by `connect` to be closed gracefully
        """

        # Flywheel Client is not designed to be a context manager
        return flywheel.Client()
        # raise NotImplementedError

    def disconnect(self, session):
        """
        Gracefully close the connection session to the store generated by `connect()`

        Parameters
        ----------
        session : Any
            the session object returned by `connect` to be closed gracefully
        """
        # raise NotImplementedError

    def get_provenance(self, entry: DataEntry) -> dict[str, ty.Any]:
        """Retrieves provenance information for a given data entry in the store

        Parameters
        ----------
        entry: DataEntry
            The entry to retrieve the provenance data for

        Returns
        -------
        provenance: dict[str, Any] or None
            The provenance data stored in the repository for the data entry.
            Returns `None` if no provenance data has been stored
        """
        raise NotImplementedError

    def put_provenance(self, provenance: dict[str, ty.Any], entry: DataEntry):
        """Stores provenance information for a given data item in the store

        Parameters
        ----------
        entry: DataEntry
            The entry to store the provenance data for
        provenance: dict[str, Any]
            The provenance data to store for the data entry
        """
        raise NotImplementedError

    def create_data_tree(
        self,
        id: str,
        leaves: list[tuple[str, ...]],
        space: type,
        hierarchy: list[str],
        **kwargs,
    ):
        """Creates a new dataset within the store, then creates an empty data tree
        specified by the provided leaf IDs. Used in dataset import/exports and in
        generated dummy data for test routines

        Parameters
        ----------
        id : str
            ID of the dataset
        leaves : list[tuple[str, ...]]
            list of IDs for each leaf node to be added to the dataset. The IDs for each
            leaf should be a tuple with an ID for each level in the tree's hierarchy, e.g.
            for a hierarchy of [subject, timepoint] ->
            [("SUBJ01", "TIMEPOINT01"), ("SUBJ01", "TIMEPOINT02"), ....]
        space : type (subclass of DataSpace)
            the "space" of the dataset
        hierarchy : list[str]
            the hierarchy of the dataset to be created
        id_patterns : dict[str, str]
            Patterns for inferring IDs of rows not explicitly present in the hierarchy of
            the data tree. See ``DataStore.infer_ids()`` for syntax
        **kwargs
            Not used, but should be kept here to allow compatibility with future
            stores that may need to be passed other arguments
        """
        with self.connection:

            group = self.connection.get("arcana_tests")
            project = group.add_project(label=id)
            for ids_tuple in leaves:
                logger.debug(ids_tuple)
                subject_id, session_id = ids_tuple
                try:
                    # Create subject
                    subject = project.add_subject(label=f"{subject_id}")
                except flywheel.ApiException:
                    # subject already exists
                    continue
                # Create session
                subject.add_session(label=f"{session_id}")

    ################################
    # RemoteStore-specific methods #
    ################################

    def download_files(self, entry: DataEntry, download_dir: Path) -> Path:
        """Download files associated with the given entry in the data store, using
        `download_dir` as temporary storage location (will be monitored by downloads
        in sibling processes to detect if download activity has stalled), return the
        path to a directory containing only the downloaded files

        Parameters
        ----------
        entry : DataEntry
            entry in the data store to download the files/directories from
        download_dir : Path
            temporary storage location for the downloaded files and/or compressed
            archives. It will be monitored by sibling processes to detect if download
            activity has stalled, therefore should be used during the download process
            (i.e. not just copied to at the end).

        Returns
        -------
        output_dir : Path
            a directory containing the downloaded files/directories and nothing else
        """
        raise NotImplementedError

    def upload_files(self, cache_path: Path, entry: DataEntry):
        """Upload all files contained within `input_dir` to the specified entry in the
        data store

        Parameters
        ----------
        cache_path : Path
            directory containing the files/directories to be uploaded
        entry : DataEntry
            the entry in the data store to upload the files to
        """

        if "@" in entry.uri:
            analysis = self.connection.get(entry.uri)
            analysis.upload_output(cache_path)
        else:
            acquisition = self.connection.get(entry.uri)
            acquisition.upload_file(cache_path)

    def download_value(
        self, entry: DataEntry
    ) -> ty.Union[float, int, str, list[float], list[int], list[str]]:
        """
        Extract and return the value of the field from the store

        Parameters
        ----------
        entry : DataEntry
            The data entry to retrieve the value from

        Returns
        -------
        value : float or int or str or list[float] or list[int] or list[str]
            The value of the Field
        """
        raise NotImplementedError

    def upload_value(
        self,
        value: ty.Union[float, int, str, list[float], list[int], list[str]],
        entry: DataEntry,
    ):
        """Store the value for a field in the XNAT repository

        Parameters
        ----------
        value : ty.Union[float, int, str, list[float], list[int], list[str]]
            the value to store in the entry
        entry : DataEntry
            the entry to store the value in
        """
        raise NotImplementedError

    def create_fileset_entry(
        self, path: str, datatype: type, row: DataRow
    ) -> DataEntry:
        """
        Creates a new data entry to store a file-set

        Parameters
        ----------
        path: str
            the path to the entry relative to the row
        datatype : type
            the datatype of the entry
        row : DataRow
            the row of the data entry

        Returns
        -------
        entry : DataEntry
            the created entry for the field
        """

        # Determine level (proj, sub, sess)
        fwrow = determine_fwrow(row)  # noqa

        if "@" in entry.uri:  # noqa
            # file_refs refer to to the input files used to generate the
            # analysis results
            # calculate with: file_ref = acquisition.get_file("FILENAME").ref()
            file_refs = "it worked"
            analysis = fwrow.add_analysis(label=row.label, inputs=[file_refs])
            fw_id = analysis.id
        else:
            # COPY XNAT EXCEPTION
            acquisition = fwrow.add_acquisition(f"label={row.label}")
            fw_id = acquisition.id

        logger.debug("Created entry %s", fw_id)
        # Add corresponding entry to row
        entry = row.add_entry(
            path=path,
            datatype=datatype,
            uri=fw_id,
        )
        return entry

    def create_field_entry(self, path: str, datatype: type, row: DataRow) -> DataEntry:
        """
        Creates a new data entry to store a field

        Parameters
        ----------
        path: str
            the path to the entry relative to the row
        datatype : type
            the datatype of the entry
        row : DataRow
            the row of the data entry

        Returns
        -------
        entry : DataEntry
            the created entry for the field
        """
        raise NotImplementedError

    def get_checksums(self, uri: str) -> dict[str, str]:
        """
        Downloads the checksum digests associated with the files in the file-set.
        These are saved with the downloaded files in the cache and used to
        check if the files have been updated on the server

        Parameters
        ----------
        uri: str
            uri of the data item to download the checksums for

        Returns
        -------
        checksums : dict[str, str]
            the checksums downloaded from the remote store. Keys are the
            paths of the files and the values are the checksums of their contents
        """
        raise NotImplementedError

    def calculate_checksums(self, fileset: FileSet) -> dict[str, str]:
        """
        Calculates the checksum digests associated with the files in the file-set.
        These checksums should match the cryptography method used by the remote store
        (e.g. MD5, SHA256)

        Parameters
        ----------
        uri: str
            uri of the data item to download the checksums for

        Returns
        -------
        checksums : dict[str, str]
            the checksums calculated from the local file-set. Keys are the
            paths of the files and the values are the checksums of their contents
        """
        raise NotImplementedError

    ##################
    # Helper methods #
    ##################

    def get_fwrow(self, row: DataRow):
        """ """

        with self.connection:
            fwproject = self.connection.lookup(f"arcana_tests/{row.dataset.id}")
            # Check level in hierarchy
            if row.frequency == Clinical.dataset:
                fwrow = fwproject
            elif row.frequency == Clinical.subject:
                fwrow = fwproject.get(row.frequency_id("subject"))
            elif row.frequency == Clinical.session:
                fwrow = fwproject.get(row.frequency_id("session"))
            else:
                raise NotImplementedError

            return fwrow
