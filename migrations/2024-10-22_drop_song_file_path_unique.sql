-- Remove the UNIQUE constraint on songs.file_path so multiple rows can point
-- to the same path (e.g., reprocessed versions or alternative mixes).

ALTER TABLE songs
    DROP CONSTRAINT IF EXISTS songs_file_path_key;
