"""Unit tests for boring_ui.api.storage module."""
import pytest
from pathlib import Path
from boring_ui.api.storage import Storage, LocalStorage


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace with test files."""
    # Create test files
    (tmp_path / 'file1.txt').write_text('content1')
    (tmp_path / 'file2.txt').write_text('content2')
    (tmp_path / 'subdir').mkdir()
    (tmp_path / 'subdir' / 'nested.txt').write_text('nested content')
    return tmp_path


class TestLocalStorage:
    """Tests for LocalStorage class."""

    def test_init(self, temp_workspace):
        """Test storage initialization."""
        storage = LocalStorage(temp_workspace)
        assert storage.root == temp_workspace.resolve()

    def test_list_dir_root(self, temp_workspace):
        """Test listing root directory."""
        storage = LocalStorage(temp_workspace)
        entries = storage.list_dir(Path('.'))
        names = [e['name'] for e in entries]
        assert 'file1.txt' in names
        assert 'file2.txt' in names
        assert 'subdir' in names

    def test_list_dir_subdir(self, temp_workspace):
        """Test listing subdirectory."""
        storage = LocalStorage(temp_workspace)
        entries = storage.list_dir(Path('subdir'))
        assert len(entries) == 1
        assert entries[0]['name'] == 'nested.txt'
        assert entries[0]['is_dir'] is False

    def test_list_dir_sorted(self, temp_workspace):
        """Test that entries are sorted (directories first, then alphabetically)."""
        storage = LocalStorage(temp_workspace)
        entries = storage.list_dir(Path('.'))
        # Directories should come first
        dirs = [e for e in entries if e['is_dir']]
        files = [e for e in entries if not e['is_dir']]
        assert dirs == entries[:len(dirs)]
        # First entry should be 'subdir' (the only directory)
        assert entries[0]['name'] == 'subdir'
        assert entries[0]['is_dir'] is True

    def test_list_dir_empty(self, tmp_path):
        """Test listing empty directory."""
        storage = LocalStorage(tmp_path)
        entries = storage.list_dir(Path('.'))
        assert entries == []

    def test_list_dir_missing_returns_empty(self, temp_workspace):
        """Test that listing non-existent directory returns empty list."""
        storage = LocalStorage(temp_workspace)
        entries = storage.list_dir(Path('nonexistent'))
        assert entries == []

    def test_list_dir_includes_size(self, temp_workspace):
        """Test that file entries include size."""
        storage = LocalStorage(temp_workspace)
        entries = storage.list_dir(Path('.'))
        file_entries = [e for e in entries if not e['is_dir']]
        for entry in file_entries:
            assert 'size' in entry
            assert isinstance(entry['size'], int)

    def test_read_file(self, temp_workspace):
        """Test reading file contents."""
        storage = LocalStorage(temp_workspace)
        content = storage.read_file(Path('file1.txt'))
        assert content == 'content1'

    def test_read_file_nested(self, temp_workspace):
        """Test reading nested file."""
        storage = LocalStorage(temp_workspace)
        content = storage.read_file(Path('subdir/nested.txt'))
        assert content == 'nested content'

    def test_read_file_not_found(self, temp_workspace):
        """Test reading non-existent file raises error."""
        storage = LocalStorage(temp_workspace)
        with pytest.raises(FileNotFoundError):
            storage.read_file(Path('nonexistent.txt'))

    def test_write_file(self, temp_workspace):
        """Test writing file."""
        storage = LocalStorage(temp_workspace)
        storage.write_file(Path('new.txt'), 'new content')
        assert (temp_workspace / 'new.txt').read_text() == 'new content'

    def test_write_file_creates_parents(self, temp_workspace):
        """Test writing file creates parent directories."""
        storage = LocalStorage(temp_workspace)
        storage.write_file(Path('new/nested/file.txt'), 'deep content')
        assert (temp_workspace / 'new/nested/file.txt').read_text() == 'deep content'

    def test_write_file_overwrites(self, temp_workspace):
        """Test writing file overwrites existing content."""
        storage = LocalStorage(temp_workspace)
        storage.write_file(Path('file1.txt'), 'updated content')
        assert (temp_workspace / 'file1.txt').read_text() == 'updated content'

    def test_delete_file(self, temp_workspace):
        """Test deleting file."""
        storage = LocalStorage(temp_workspace)
        storage.delete(Path('file1.txt'))
        assert not (temp_workspace / 'file1.txt').exists()

    def test_delete_directory(self, temp_workspace):
        """Test deleting directory recursively."""
        storage = LocalStorage(temp_workspace)
        storage.delete(Path('subdir'))
        assert not (temp_workspace / 'subdir').exists()

    def test_delete_not_found(self, temp_workspace):
        """Test deleting non-existent path raises error."""
        storage = LocalStorage(temp_workspace)
        with pytest.raises(FileNotFoundError):
            storage.delete(Path('nonexistent.txt'))

    def test_rename_file(self, temp_workspace):
        """Test renaming file."""
        storage = LocalStorage(temp_workspace)
        storage.rename(Path('file1.txt'), Path('renamed.txt'))
        assert not (temp_workspace / 'file1.txt').exists()
        assert (temp_workspace / 'renamed.txt').read_text() == 'content1'

    def test_rename_directory(self, temp_workspace):
        """Test renaming directory."""
        storage = LocalStorage(temp_workspace)
        storage.rename(Path('subdir'), Path('renamed_dir'))
        assert not (temp_workspace / 'subdir').exists()
        assert (temp_workspace / 'renamed_dir').is_dir()
        assert (temp_workspace / 'renamed_dir/nested.txt').exists()

    def test_rename_not_found(self, temp_workspace):
        """Test renaming non-existent path raises error."""
        storage = LocalStorage(temp_workspace)
        with pytest.raises(FileNotFoundError):
            storage.rename(Path('nonexistent.txt'), Path('new.txt'))

    def test_rename_target_exists(self, temp_workspace):
        """Test renaming to existing path raises error."""
        storage = LocalStorage(temp_workspace)
        with pytest.raises(FileExistsError):
            storage.rename(Path('file1.txt'), Path('file2.txt'))

    def test_move_file(self, temp_workspace):
        """Test moving file to different directory."""
        storage = LocalStorage(temp_workspace)
        new_path = storage.move(Path('file1.txt'), Path('subdir'))
        assert not (temp_workspace / 'file1.txt').exists()
        assert (temp_workspace / 'subdir/file1.txt').exists()
        assert new_path == Path('subdir/file1.txt')

    def test_move_not_found(self, temp_workspace):
        """Test moving non-existent file raises error."""
        storage = LocalStorage(temp_workspace)
        with pytest.raises(FileNotFoundError):
            storage.move(Path('nonexistent.txt'), Path('subdir'))

    def test_move_dest_not_directory(self, temp_workspace):
        """Test moving to non-directory raises error."""
        storage = LocalStorage(temp_workspace)
        with pytest.raises(NotADirectoryError):
            storage.move(Path('file1.txt'), Path('file2.txt'))

    def test_move_target_exists(self, temp_workspace):
        """Test moving to existing target raises error."""
        storage = LocalStorage(temp_workspace)
        # Create a file with the same name in subdir
        (temp_workspace / 'subdir/file1.txt').write_text('existing')
        with pytest.raises(FileExistsError):
            storage.move(Path('file1.txt'), Path('subdir'))

    def test_exists_file(self, temp_workspace):
        """Test exists returns True for existing file."""
        storage = LocalStorage(temp_workspace)
        assert storage.exists(Path('file1.txt')) is True

    def test_exists_directory(self, temp_workspace):
        """Test exists returns True for existing directory."""
        storage = LocalStorage(temp_workspace)
        assert storage.exists(Path('subdir')) is True

    def test_exists_not_found(self, temp_workspace):
        """Test exists returns False for non-existent path."""
        storage = LocalStorage(temp_workspace)
        assert storage.exists(Path('nonexistent.txt')) is False


class TestLocalStorageSecurity:
    """Security tests for LocalStorage path validation."""

    def test_path_traversal_rejected(self, temp_workspace):
        """Test that path traversal is rejected."""
        storage = LocalStorage(temp_workspace)
        with pytest.raises(ValueError):
            storage.read_file(Path('../../../etc/passwd'))

    def test_absolute_path_outside_rejected(self, temp_workspace):
        """Test that absolute paths outside workspace are rejected."""
        storage = LocalStorage(temp_workspace)
        with pytest.raises(ValueError):
            storage.read_file(Path('/etc/passwd'))

    def test_write_traversal_rejected(self, temp_workspace):
        """Test that write path traversal is rejected."""
        storage = LocalStorage(temp_workspace)
        with pytest.raises(ValueError):
            storage.write_file(Path('../malicious.txt'), 'bad content')

    def test_delete_traversal_rejected(self, temp_workspace):
        """Test that delete path traversal is rejected."""
        storage = LocalStorage(temp_workspace)
        with pytest.raises(ValueError):
            storage.delete(Path('../important'))
