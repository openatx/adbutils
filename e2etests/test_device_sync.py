
import filecmp
import os
import pathlib

from adbutils import AdbDevice


# todo: make independent of already present stuff on the phone
def test_pull_push_dirs(
        device: AdbDevice,
        device_tmp_dir_path: str,
        local_src_in_dir: pathlib.Path,
        tmp_path: pathlib.Path,
):
    def are_dir_trees_equal(dir1, dir2):
        """
        Compare two directories recursively. Files in each directory are
        assumed to be equal if their names and contents are equal.

        NB: retreived from: https://stackoverflow.com/a/6681395

        @param dir1: First directory path
        @param dir2: Second directory path

        @return: True if the directory trees are the same and 
            there were no errors while accessing the directories or files, 
            False otherwise.
        """

        dirs_cmp = filecmp.dircmp(dir1, dir2)
        if len(dirs_cmp.left_only) > 0 or len(dirs_cmp.right_only) > 0 or \
                len(dirs_cmp.funny_files) > 0:
            return False
        (_, mismatch, errors) = filecmp.cmpfiles(
            dir1, dir2, dirs_cmp.common_files, shallow=False)
        if len(mismatch) > 0 or len(errors) > 0:
            return False
        for common_dir in dirs_cmp.common_dirs:
            new_dir1 = os.path.join(dir1, common_dir)
            new_dir2 = os.path.join(dir2, common_dir)
            if not are_dir_trees_equal(new_dir1, new_dir2):
                return False
        return True

    local_src_out_dir1 = tmp_path / 'dir1'
    local_src_out_dir2 = tmp_path / 'dir2'

    # TODO: push src support dir
    # device.push(local_src_in_dir, device_tmp_dir_path)
    device.adb_output("push", str(local_src_in_dir), device_tmp_dir_path)

    device.sync.pull_dir(device_tmp_dir_path, local_src_out_dir1)

    assert local_src_out_dir1.exists()
    assert local_src_out_dir1.is_dir()

    are_dir_trees_equal(local_src_in_dir, local_src_out_dir1)

    device.sync.pull(device_tmp_dir_path, local_src_out_dir2)

    assert local_src_out_dir2.exists()
    assert local_src_out_dir2.is_dir()

    are_dir_trees_equal(local_src_in_dir, local_src_out_dir2)
