"""
Entity Mapping Service to resolve and map entities from different data sources.
Includes a manual review queue for uncertain matches.
"""

import json
from typing import Any

from thefuzz import fuzz

# Assume DatabaseManager is in src.database.manager
# from src.database.manager import DatabaseManager


class EntityMapper:
    """
    Handles entity resolution, including a review queue for uncertain matches.
    """

    def __init__(self, db_manager: Any):
        self.db_manager = db_manager
        # High confidence threshold for automatic matching
        self.MATCH_THRESHOLD = 90
        # Lower threshold to flag an entity for manual review
        self.REVIEW_THRESHOLD = 75  # Anything between 75 and 90 will be reviewed

        self.strategies = {
            "team": {
                "table": "teams",
                "match_fields": ["name", "country_id"],
                "fuzzy_fields": ["name"],
            },
            "player": {
                "table": "players",
                "match_fields": ["last_name", "first_name", "birth_date"],
                "fuzzy_fields": ["first_name", "last_name"],
            },
            # ... other strategies
        }

    async def _find_best_match(
        self, entity_type: str, new_entity_data: dict
    ) -> tuple[int | None, float]:
        """
        Finds the best matching record and returns its ID and confidence score.
        """
        strategy = self.strategies[entity_type]
        table = strategy["table"]

        query = f"SELECT id, {', '.join(strategy['match_fields'])} FROM {table};"
        all_entities = await self.db_manager.execute_query(query)

        best_match_id = None
        highest_score = 0.0

        for existing_entity in all_entities:
            # Calculate a score based on all fields
            total_similarity = 0
            field_count = len(strategy["match_fields"])

            for field in strategy["match_fields"]:
                new_value = new_entity_data.get(field)
                existing_value = existing_entity.get(field)

                if new_value is None or existing_value is None:
                    continue  # Or handle differently

                if field in strategy["fuzzy_fields"]:
                    total_similarity += fuzz.ratio(
                        str(new_value).lower(), str(existing_value).lower()
                    )
                else:
                    if new_value == existing_value:
                        total_similarity += 100  # Perfect match for exact fields

            # Average score across all fields
            current_score = total_similarity / field_count if field_count > 0 else 0

            if current_score > highest_score:
                highest_score = current_score
                best_match_id = existing_entity["id"]

        return best_match_id, highest_score

    async def _log_for_review(
        self,
        entity_type: str,
        source_name: str,
        new_entity_data: dict,
        potential_match_id: int,
        score: float,
    ):
        """Logs an uncertain match into the review queue table."""
        query = """
                INSERT INTO mapping_review_queue
                (entity_type, source_name, new_entity_data, potential_match_id, confidence_score)
                VALUES ($1, $2, $3, $4, $5); \
                """
        await self.db_manager.execute_query(
            query,
            entity_type,
            source_name,
            json.dumps(new_entity_data, default=str),  # Serialize data to JSON string
            potential_match_id,
            score,
        )
        print(
            f"Logged uncertain match for {entity_type} from '{source_name}' for review. Score: {score:.2f}"
        )

    async def find_or_create(
        self, entity_type: str, new_entity_data: dict, source_name: str, source_id: str
    ) -> int | None:
        """
        Processes an entity: matches, creates, or sends to review queue.
        Returns the internal ID if resolved, otherwise None.
        """
        match_id, score = await self._find_best_match(entity_type, new_entity_data)

        if match_id and score >= self.MATCH_THRESHOLD:
            # Case 1: High confidence match -> Merge automatically
            print(f"Confident match found (Score: {score:.2f}). Merging...")
            table = self.strategies[entity_type]["table"]
            update_query = f"""
                UPDATE {table}
                SET external_ids = jsonb_set(COALESCE(external_ids, '{{}}'), '{{{source_name}}}', '"{source_id}"', true)
                WHERE id = $1;
            """
            await self.db_manager.execute_query(update_query, match_id)
            return match_id

        elif match_id and score >= self.REVIEW_THRESHOLD:
            # Case 2: Uncertain match -> Log for manual review
            await self._log_for_review(
                entity_type,
                source_name,
                {**new_entity_data, "source_id": source_id},
                match_id,
                score,
            )
            return None  # Not resolved yet

        else:
            # Case 3: No confident match -> Create a new record
            print(f"No match found (Best score: {score:.2f}). Creating new record.")
            table = self.strategies[entity_type]["table"]
            new_entity_data["external_ids"] = json.dumps({source_name: source_id})

            columns = ", ".join(new_entity_data.keys())
            placeholders = ", ".join([f"${i + 1}" for i in range(len(new_entity_data))])

            insert_query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING id;"
            new_id = await self.db_manager.execute_insert(insert_query, *new_entity_data.values())
            return new_id

    # --- Methods for Manual Review Process ---

    async def get_pending_reviews(self, entity_type: str | None = None) -> list[dict]:
        """Fetches all pending review items from the queue."""
        query = "SELECT * FROM mapping_review_queue WHERE status = 'pending'"
        params = []
        if entity_type:
            query += " AND entity_type = $1"
            params.append(entity_type)
        query += " ORDER BY created_at;"

        return await self.db_manager.execute_query(query, *params)

    async def resolve_review_item(
        self, review_id: int, decision: str, target_id: int | None = None
    ):
        """
        Resolves a review item based on a manual decision.

        Args:
            review_id: The ID of the item in the mapping_review_queue.
            decision: The manual decision ('merge', 'create', 'discard').
            target_id: The internal ID to merge with (required for 'merge' decision).
        """
        review_item = await self.db_manager.execute_query(
            "SELECT * FROM mapping_review_queue WHERE id = $1", review_id
        )
        if not review_item:
            raise ValueError("Review item not found.")
        review_item = review_item[0]

        entity_type = review_item["entity_type"]
        source_name = review_item["source_name"]
        new_data = review_item["new_entity_data"]
        source_id = new_data.pop("source_id")  # Extract source_id added earlier
        table = self.strategies[entity_type]["table"]

        if decision == "merge":
            if not target_id:
                raise ValueError("Target ID is required for merge decision.")
            # Merge with the specified existing entity
            update_query = f"""
                UPDATE {table}
                SET external_ids = jsonb_set(COALESCE(external_ids, '{{}}'), '{{{source_name}}}', '"{source_id}"', true)
                WHERE id = $1;
            """
            await self.db_manager.execute_query(update_query, target_id)

        elif decision == "create":
            # Create a new entity
            new_data["external_ids"] = json.dumps({source_name: source_id})
            columns = ", ".join(new_data.keys())
            placeholders = ", ".join([f"${i + 1}" for i in range(len(new_data))])
            insert_query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders});"
            await self.db_manager.execute_query(insert_query, *new_data.values())

        elif decision == "discard":
            # Do nothing with the main tables, just update the queue status
            pass

        else:
            raise ValueError("Invalid decision. Must be 'merge', 'create', or 'discard'.")

        # Update the review item status
        await self.db_manager.execute_query(
            "UPDATE mapping_review_queue SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP WHERE id = $1",
            review_id,
        )
        print(f"Review item {review_id} resolved with decision: '{decision}'.")
