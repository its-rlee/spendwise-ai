BEGIN;

ALTER TABLE spendwise.transaction_items
ADD COLUMN IF NOT EXISTS
    raw_description VARCHAR(255);

ALTER TABLE spendwise.transaction_items
ADD COLUMN IF NOT EXISTS
    store_item_code VARCHAR(64);

ALTER TABLE spendwise.transaction_items
ADD COLUMN IF NOT EXISTS
    source_line_index INTEGER;

COMMIT;
