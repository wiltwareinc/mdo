from pathlib import Path

from models.file_manager import FileManager


def main() -> None:
    fm = FileManager(Path("music"))

    print(f"Songs: {len(fm.songs)}")
    print("First song:", fm.songs[0] if fm.songs else "none")

    albums = fm.read_albums()
    print(f"Albums: {len(albums)}")
    print("First album:", albums[0] if albums else "none")

    required_song = {"slug", "title", "lyrics_count", "projects_count", "renders_count"}
    for song in fm.songs:
        missing = required_song - song.keys()
        if missing:
            print("Missing song keys:", song.get("slug"), missing)

    required_album = {"slug", "name", "tracklist", "created_at", "modified_at"}
    for album in albums:
        missing = required_album - album.keys()
        if missing:
            print("Missing album keys:", album.get("slug"), missing)


if __name__ == "__main__":
    main()
