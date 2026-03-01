-- Store whether the group message is text or photo (caption) for correct edit method
ALTER TABLE request_messages ADD COLUMN content_type TEXT DEFAULT 'text';
