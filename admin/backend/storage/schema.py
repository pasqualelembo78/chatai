import logging
from db import get_conn, put_conn

logger = logging.getLogger(__name__)

def init_db():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                user_id TEXT NOT NULL,
                character_id TEXT NOT NULL,
                trust REAL DEFAULT 0,
                affinity REAL DEFAULT 0,
                respect REAL DEFAULT 0,
                conflict REAL DEFAULT 0,
                intimacy REAL DEFAULT 0,
                pressure_level REAL DEFAULT 0,
                PRIMARY KEY (user_id, character_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS personality (
                character_id TEXT PRIMARY KEY,
                warmth REAL DEFAULT 5,
                strictness REAL DEFAULT 5,
                patience REAL DEFAULT 5,
                sarcasm REAL DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS world_state (
                id INTEGER PRIMARY KEY DEFAULT 1,
                scene TEXT DEFAULT 'default',
                events TEXT DEFAULT '[]',
                flags TEXT DEFAULT '{}'
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                character_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS conversation_memory (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                character_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                topics TEXT DEFAULT '[]',
                message_count INTEGER DEFAULT 0,
                relationship_snapshot TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS personality_shifts (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                character_id TEXT NOT NULL,
                pressure_type TEXT,
                pressure_level REAL,
                deltas TEXT DEFAULT '{}',
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_memory (
                user_id TEXT PRIMARY KEY,
                memory_data TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_characters (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                age INTEGER DEFAULT 0,
                role TEXT DEFAULT '',
                category TEXT DEFAULT '',
                avatar TEXT DEFAULT '💬',
                description TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                is_adult INTEGER DEFAULT 0,
                essence TEXT DEFAULT '',
                personality TEXT DEFAULT '',
                speaking_style TEXT DEFAULT '',
                backstory TEXT DEFAULT '',
                hobbies TEXT DEFAULT '[]',
                system_prompt TEXT DEFAULT '',
                core_traits TEXT DEFAULT '{}',
                intimacy_config TEXT DEFAULT '{}',
                refusal_style TEXT DEFAULT 'dolce',
                evolution TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            INSERT INTO world_state (id, scene, events, flags)
            VALUES (1, 'default', '[]', '{}')
            ON CONFLICT (id) DO NOTHING
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS premium_users (
                user_id TEXT PRIMARY KEY,
                is_premium INTEGER DEFAULT 0,
                sku TEXT DEFAULT '',
                purchase_token TEXT DEFAULT '',
                activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS character_evolution (
                user_id TEXT NOT NULL,
                character_id TEXT NOT NULL,
                current_stage TEXT DEFAULT 'base',
                unlocked_stages TEXT DEFAULT '["base"]',
                flags TEXT DEFAULT '{}',
                trait_modifiers TEXT DEFAULT '{}',
                intimacy_peak REAL DEFAULT 0,
                total_messages INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, character_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id TEXT,
                action TEXT NOT NULL,
                detail TEXT DEFAULT '',
                ip TEXT DEFAULT '',
                user_agent TEXT DEFAULT ''
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS moderation_flags (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                flagged_by TEXT NOT NULL DEFAULT 'system',
                reason TEXT NOT NULL,
                content_type TEXT DEFAULT '',
                content_snippet TEXT DEFAULT '',
                severity TEXT DEFAULT 'medium',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT PRIMARY KEY,
                gender_interest TEXT DEFAULT '',
                age_range TEXT DEFAULT '',
                interest_tags TEXT DEFAULT '[]',
                show_adult INTEGER DEFAULT 0,
                user_gender TEXT DEFAULT '',
                user_age INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS mevacoins (
                user_id TEXT PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS mevacoins_transactions (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                amount INTEGER NOT NULL,
                reason TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS daily_checkins (
                user_id TEXT NOT NULL,
                checkin_date TEXT NOT NULL,
                redeemed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, checkin_date)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS new_user_bonus (
                user_id TEXT NOT NULL,
                day_number INTEGER NOT NULL,
                claimed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, day_number)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS content_unlocks (
                user_id TEXT NOT NULL,
                content_type TEXT NOT NULL,
                content_id TEXT NOT NULL,
                spent_amount INTEGER NOT NULL,
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, content_type, content_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS referral_codes (
                user_id TEXT PRIMARY KEY,
                code TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS referral_earnings (
                referrer_id TEXT NOT NULL,
                referred_id TEXT NOT NULL,
                bonus_type TEXT NOT NULL,
                amount INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (referrer_id, referred_id, bonus_type)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_shares (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                share_date TEXT NOT NULL,
                platform TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS streak_milestones (
                user_id TEXT NOT NULL,
                milestone INTEGER NOT NULL,
                claimed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, milestone)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS streak_30days (
                user_id TEXT NOT NULL,
                day_number INTEGER NOT NULL,
                claimed INTEGER DEFAULT 0,
                claimed_at TIMESTAMP,
                PRIMARY KEY (user_id, day_number)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_user_char ON messages(user_id, character_id)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS character_demographics (
                character_id TEXT PRIMARY KEY,
                gender TEXT DEFAULT '',
                gender_display TEXT DEFAULT '',
                sexual_orientation TEXT DEFAULT 'etero',
                sexual_orientation_display TEXT DEFAULT 'eterosessuale',
                birth_date TEXT DEFAULT '',
                birth_place TEXT DEFAULT '',
                species TEXT DEFAULT 'umano',
                age_static INTEGER DEFAULT 0
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_demo_gender ON character_demographics(gender)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_demo_species ON character_demographics(species)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_demo_orientation ON character_demographics(sexual_orientation)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS character_birthdays (
                character_id TEXT PRIMARY KEY,
                last_notified TEXT DEFAULT ''
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS time_events (
                id SERIAL PRIMARY KEY,
                event_type TEXT NOT NULL,
                character_id TEXT,
                user_id TEXT,
                data TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ─── Phase 2: Per-user personality ───────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_personality (
                user_id TEXT NOT NULL,
                character_id TEXT NOT NULL,
                warmth REAL DEFAULT 5,
                strictness REAL DEFAULT 5,
                patience REAL DEFAULT 5,
                sarcasm REAL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, character_id)
            )
        """)

        # ─── Phase 2: Per-user world state ──────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_world_state (
                user_id TEXT PRIMARY KEY,
                scene TEXT DEFAULT 'default',
                events TEXT DEFAULT '[]',
                flags TEXT DEFAULT '{}',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ─── Phase 3: Enhanced user memory with importance + decay ───
        cur.execute("""
            ALTER TABLE user_memory ADD COLUMN IF NOT EXISTS memory_version INTEGER DEFAULT 1
        """)

        # ─── Phase 5: Conversation session tracking ──────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS conversation_sessions (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                character_id TEXT NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                topic_summary TEXT DEFAULT ''
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_char ON conversation_sessions(user_id, character_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_last_msg ON conversation_sessions(last_message_at)")

        # ─── Phase 7: Cross-character shared memory ──────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS shared_memory (
                user_id TEXT NOT NULL,
                fact_key TEXT NOT NULL,
                fact_value TEXT NOT NULL,
                source_characters TEXT DEFAULT '[]',
                importance REAL DEFAULT 0.5,
                mentions INTEGER DEFAULT 1,
                last_mentioned TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, fact_key)
            )
        """)

        # ─── Phase 8: Conversation topics ────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS conversation_topics (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                character_id TEXT NOT NULL,
                topic TEXT NOT NULL,
                message_count INTEGER DEFAULT 1,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, character_id, topic)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_topics_user_char ON conversation_topics(user_id, character_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_topics_last_seen ON conversation_topics(last_seen)")

        # ─── Phase 4: Semantic memory (pgvector) ─────────────────────
        # Will be created separately if pgvector is available
        try:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memory_embeddings (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    character_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_type TEXT NOT NULL DEFAULT 'message',
                    embedding vector(384),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_emb_user_char ON memory_embeddings(user_id, character_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_emb_user ON memory_embeddings(user_id)")
            logger.info("pgvector extension loaded, semantic search available")
        except Exception as e:
            logger.warning(f"pgvector not available, semantic search disabled: {e}")
            conn.rollback()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS admin_dms (
                id SERIAL PRIMARY KEY,
                from_user_id TEXT NOT NULL,
                to_user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                read_at TIMESTAMP NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_admin_dms_to ON admin_dms(to_user_id, read_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_admin_dms_from ON admin_dms(from_user_id, created_at)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS group_chats (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS group_chat_characters (
                group_chat_id INTEGER NOT NULL REFERENCES group_chats(id) ON DELETE CASCADE,
                character_id TEXT NOT NULL,
                PRIMARY KEY (group_chat_id, character_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS group_chat_messages (
                id SERIAL PRIMARY KEY,
                group_chat_id INTEGER NOT NULL REFERENCES group_chats(id) ON DELETE CASCADE,
                sender_type TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_gcm_chat ON group_chat_messages(group_chat_id, timestamp)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_gcc_chat ON group_chat_characters(group_chat_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_gc_user ON group_chats(user_id)")

        conn.commit()
    finally:
        put_conn(conn)

def init_group_chat_tables():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS group_chats (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS group_chat_characters (
                group_chat_id INTEGER NOT NULL REFERENCES group_chats(id) ON DELETE CASCADE,
                character_id TEXT NOT NULL,
                PRIMARY KEY (group_chat_id, character_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS group_chat_messages (
                id SERIAL PRIMARY KEY,
                group_chat_id INTEGER NOT NULL REFERENCES group_chats(id) ON DELETE CASCADE,
                sender_type TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS group_chat_participants (
                group_chat_id INTEGER NOT NULL REFERENCES group_chats(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (group_chat_id, user_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS group_chat_invitations (
                id SERIAL PRIMARY KEY,
                group_chat_id INTEGER NOT NULL REFERENCES group_chats(id) ON DELETE CASCADE,
                inviter_id TEXT NOT NULL,
                invitee_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                responded_at TIMESTAMP,
                UNIQUE(group_chat_id, invitee_id)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_gcm_chat ON group_chat_messages(group_chat_id, timestamp)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_gcc_chat ON group_chat_characters(group_chat_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_gc_user ON group_chats(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_gcp_chat ON group_chat_participants(group_chat_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_gcp_user ON group_chat_participants(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_gci_invitee ON group_chat_invitations(invitee_id, status)")
        conn.commit()
    finally:
        put_conn(conn)