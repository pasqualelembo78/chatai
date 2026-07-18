"""Storage layer — re-exports all public symbols for backward compatibility."""

from storage.crypto import _get_master_key, encrypt_value, decrypt_value
from storage.schema import init_db, init_group_chat_tables
from storage.relationships import (
    get_relationship, update_relationship,
    update_intimacy, update_pressure_level, describe_intimacy_level,
)
from storage.personalities import (
    get_personality, update_personality,
    record_personality_shift, get_recent_shifts, describe_personality,
    get_user_personality, update_user_personality, set_user_personality,
)
from storage.world_state import (
    get_world_state, save_world_state,
    get_user_world_state, save_user_world_state,
)
from storage.messages import (
    add_message, get_recent_messages, count_messages,
    has_scenario_message, count_all_user_messages,
    add_time_event, get_time_events,
)
from storage.memories import (
    add_memory, get_memories, get_last_summary_checkpoint,
    get_user_memory, update_user_memory, reset_user_memory,
    reset_conversation, reset_all_user_data,
    update_user_memory_enhanced, decay_user_memory, get_relevant_memories,
    consolidate_user_memory,
)
from storage.embeddings import (
    store_embedding, search_similar_memories, get_embedding_count,
)
from storage.user_accounts import (
    create_user_character, get_user_character, get_user_characters,
    get_all_user_characters, delete_user_character,
    is_user_premium, set_user_premium,
    user_exists, update_user_role,
    block_user, unblock_user, get_blocked_users, is_blocked,
)
from storage.moderation import (
    flag_user, get_moderation_flags,
    resolve_moderation_flag, get_flag_count,
)
from storage.analytics import (
    get_all_users, ban_user, export_user_data, delete_user,
    get_admin_stats, search_users, get_user_detail,
    list_user_conversations, get_user_conversation_messages,
)
from storage.dm import (
    send_admin_dm, list_admin_dms, mark_admin_dms_read,
)
from storage.group_chat import (
    create_group_chat, list_group_chats, get_group_chat,
    delete_group_chat, add_group_character, remove_group_character,
    add_group_participant, remove_group_participant,
    get_group_participants, is_group_participant,
    create_group_invitation, get_user_pending_invitations,
    respond_to_invitation, get_invitation_status,
    get_user_group_chats, add_group_message, get_group_messages,
)
from storage.evolution import (
    get_evolution, update_evolution,
    start_conversation_session, get_temporal_context,
)
from storage.preferences import (
    get_user_preferences, save_user_preferences, derive_sexual_orientation,
    set_verified_birth_year, is_age_verified,
)
from storage.mevacoins import (
    get_mevacoins_balance, add_mevacoins,
    spend_mevacoins, get_mevacoins_transactions,
)
from storage.streak import (
    daily_checkin, redeem_daily_checkin,
    get_checkin_streak, claim_streak_milestone,
    calculate_streak_reward,
    get_streak_30_status, claim_streak_30_day,
)
from storage.referrals import (
    get_or_create_referral_code, get_referrer_by_code,
    claim_referral_bonus, credit_referral_first_message,
    get_daily_share_count, add_social_share,
)
from storage.bonuses import (
    get_new_user_bonus, claim_new_user_bonus, init_new_user_bonus,
    unlock_content, is_content_unlocked, get_user_unlocks,
)
from storage.demographics import (
    get_character_demographics, update_character_demographics,
    get_characters_by_species, get_characters_by_gender,
    get_characters_by_orientation,
    get_upcoming_birthdays, register_character_birthday,
    mark_birthday_notified,
)
from storage.shared_memory import (
    share_memory_across_characters, get_shared_memories,
    TOPIC_KEYWORDS, detect_message_topics,
    update_conversation_topics, get_recent_topics,
    get_character_recent_topics,
)
from storage.pruning import (
    DEFAULT_RETENTION_DAYS, audit_log, prune_old_data,
)
from storage.message_limits import (
    DAILY_FREE_MESSAGE_LIMIT, DAILY_UNLOCK_MVC_COST,
    get_user_role, get_daily_message_status,
    check_and_count_message, refund_message, unlock_unlimited_messages,
)
