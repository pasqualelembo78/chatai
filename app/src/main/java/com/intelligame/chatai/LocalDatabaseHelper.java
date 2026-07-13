package com.intelligame.chatai;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

public class LocalDatabaseHelper extends SQLiteOpenHelper {

    private static final String DB_NAME = "chatai_local.db";
    private static final int DB_VERSION = 3;

    private static final String TABLE_MESSAGES = "messages";
    private static final String TABLE_USER_MEMORY = "user_memory";
    private static final String TABLE_USER_CHARACTERS = "user_characters";
    private static final String TABLE_EVOLUTION = "character_evolution";
    private static final String TABLE_FAVORITES = "favorites";
    private static final String TABLE_FAVORITE_HISTORY = "favorite_history";

    public LocalDatabaseHelper(Context context) {
        super(context, DB_NAME, null, DB_VERSION);
    }

    @Override
    public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE IF NOT EXISTS " + TABLE_MESSAGES + " (" +
                "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                "character_id TEXT NOT NULL, " +
                "role TEXT NOT NULL, " +
                "content TEXT NOT NULL, " +
                "timestamp INTEGER DEFAULT (strftime('%s','now')))");

        db.execSQL("CREATE TABLE IF NOT EXISTS " + TABLE_USER_MEMORY + " (" +
                "key TEXT PRIMARY KEY, " +
                "value TEXT NOT NULL)");

        db.execSQL("CREATE TABLE IF NOT EXISTS " + TABLE_USER_CHARACTERS + " (" +
                "id TEXT PRIMARY KEY, " +
                "name TEXT NOT NULL, " +
                "age INTEGER DEFAULT 0, " +
                "role TEXT DEFAULT '', " +
                "category TEXT DEFAULT '', " +
                "avatar TEXT DEFAULT '💬', " +
                "description TEXT DEFAULT '', " +
                "tags TEXT DEFAULT '[]', " +
                "is_adult INTEGER DEFAULT 0, " +
                "essence TEXT DEFAULT '', " +
                "personality TEXT DEFAULT '', " +
                "speaking_style TEXT DEFAULT '', " +
                "backstory TEXT DEFAULT '', " +
                "hobbies TEXT DEFAULT '[]', " +
                "system_prompt TEXT DEFAULT '', " +
                "created_at INTEGER DEFAULT (strftime('%s','now')))");

        db.execSQL("CREATE TABLE IF NOT EXISTS " + TABLE_EVOLUTION + " (" +
                "user_id TEXT NOT NULL, " +
                "character_id TEXT NOT NULL, " +
                "current_stage TEXT DEFAULT 'base', " +
                "unlocked_stages TEXT DEFAULT '[\"base\"]', " +
                "flags TEXT DEFAULT '{}', " +
                "trait_modifiers TEXT DEFAULT '{}', " +
                "intimacy_peak REAL DEFAULT 0, " +
                "total_messages INTEGER DEFAULT 0, " +
                "updated_at INTEGER DEFAULT (strftime('%s','now')), " +
                "PRIMARY KEY (user_id, character_id))");

        db.execSQL("CREATE TABLE IF NOT EXISTS " + TABLE_FAVORITES + " (" +
                "character_id TEXT PRIMARY KEY, " +
                "created_at INTEGER DEFAULT (strftime('%s','now')))");

        db.execSQL("CREATE TABLE IF NOT EXISTS " + TABLE_FAVORITE_HISTORY + " (" +
                "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                "character_id TEXT NOT NULL, " +
                "action TEXT NOT NULL, " +
                "created_at INTEGER DEFAULT (strftime('%s','now')))");
    }

    @Override
    public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        if (oldVersion < 2) {
            db.execSQL("CREATE TABLE IF NOT EXISTS " + TABLE_EVOLUTION + " (" +
                    "user_id TEXT NOT NULL, " +
                    "character_id TEXT NOT NULL, " +
                    "current_stage TEXT DEFAULT 'base', " +
                    "unlocked_stages TEXT DEFAULT '[\"base\"]', " +
                    "flags TEXT DEFAULT '{}', " +
                    "trait_modifiers TEXT DEFAULT '{}', " +
                    "intimacy_peak REAL DEFAULT 0, " +
                    "total_messages INTEGER DEFAULT 0, " +
                    "updated_at INTEGER DEFAULT (strftime('%s','now')), " +
                    "PRIMARY KEY (user_id, character_id))");
        }
        if (oldVersion < 3) {
            db.execSQL("CREATE TABLE IF NOT EXISTS " + TABLE_FAVORITES + " (" +
                    "character_id TEXT PRIMARY KEY, " +
                    "created_at INTEGER DEFAULT (strftime('%s','now')))");
            db.execSQL("CREATE TABLE IF NOT EXISTS " + TABLE_FAVORITE_HISTORY + " (" +
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                    "character_id TEXT NOT NULL, " +
                    "action TEXT NOT NULL, " +
                    "created_at INTEGER DEFAULT (strftime('%s','now')))");
        }
    }

    // ─── Messages ───────────────────────────────────────────────

    public void addMessage(String characterId, String role, String content) {
        SQLiteDatabase db = getWritableDatabase();
        ContentValues cv = new ContentValues();
        cv.put("character_id", characterId);
        cv.put("role", role);
        cv.put("content", content);
        db.insert(TABLE_MESSAGES, null, cv);
        db.close();
    }

    public List<JSONObject> getRecentMessages(String characterId, int limit) {
        SQLiteDatabase db = getReadableDatabase();
        List<JSONObject> list = new ArrayList<>();
        Cursor c = db.rawQuery(
                "SELECT role, content FROM " + TABLE_MESSAGES +
                " WHERE character_id=? ORDER BY timestamp ASC",
                new String[]{characterId});
        int total = c.getCount();
        int skip = Math.max(0, total - limit);
        int idx = 0;
        while (c.moveToNext()) {
            if (idx >= skip) {
                try {
                    JSONObject obj = new JSONObject();
                    obj.put("role", c.getString(c.getColumnIndexOrThrow("role")));
                    obj.put("content", c.getString(c.getColumnIndexOrThrow("content")));
                    list.add(obj);
                } catch (Exception ignored) {}
            }
            idx++;
        }
        c.close();
        db.close();
        return list;
    }

    public int getMessageCount(String characterId) {
        SQLiteDatabase db = getReadableDatabase();
        Cursor c = db.rawQuery(
                "SELECT COUNT(*) FROM " + TABLE_MESSAGES + " WHERE character_id=?",
                new String[]{characterId});
        int count = c.moveToFirst() ? c.getInt(0) : 0;
        c.close();
        db.close();
        return count;
    }

    public List<JSONObject> getAllConversations() {
        SQLiteDatabase db = getReadableDatabase();
        List<JSONObject> list = new ArrayList<>();
        Cursor c = db.rawQuery(
                "SELECT character_id, COUNT(*) as msg_count, MAX(timestamp) as last_active " +
                "FROM " + TABLE_MESSAGES + " GROUP BY character_id ORDER BY last_active DESC", null);
        while (c.moveToNext()) {
            try {
                JSONObject obj = new JSONObject();
                obj.put("character_id", c.getString(c.getColumnIndexOrThrow("character_id")));
                obj.put("msg_count", c.getInt(c.getColumnIndexOrThrow("msg_count")));
                obj.put("last_active", c.getString(c.getColumnIndexOrThrow("last_active")));
                list.add(obj);
            } catch (Exception ignored) {}
        }
        c.close();
        db.close();
        return list;
    }

    public void resetConversation(String characterId) {
        SQLiteDatabase db = getWritableDatabase();
        db.delete(TABLE_MESSAGES, "character_id=?", new String[]{characterId});
        db.close();
    }

    // ─── User Memory ────────────────────────────────────────────

    public void setUserMemory(String key, String value) {
        SQLiteDatabase db = getWritableDatabase();
        ContentValues cv = new ContentValues();
        cv.put("key", key);
        cv.put("value", value);
        db.insertWithOnConflict(TABLE_USER_MEMORY, null, cv, SQLiteDatabase.CONFLICT_REPLACE);
        db.close();
    }

    public String getUserMemory(String key) {
        SQLiteDatabase db = getReadableDatabase();
        Cursor c = db.rawQuery(
                "SELECT value FROM " + TABLE_USER_MEMORY + " WHERE key=?",
                new String[]{key});
        String val = c.moveToFirst() ? c.getString(0) : null;
        c.close();
        db.close();
        return val;
    }

    public JSONObject getAllUserMemory() {
        SQLiteDatabase db = getReadableDatabase();
        JSONObject obj = new JSONObject();
        Cursor c = db.rawQuery("SELECT key, value FROM " + TABLE_USER_MEMORY, null);
        while (c.moveToNext()) {
            try {
                obj.put(c.getString(c.getColumnIndexOrThrow("key")),
                        c.getString(c.getColumnIndexOrThrow("value")));
            } catch (Exception ignored) {}
        }
        c.close();
        db.close();
        return obj;
    }

    public void resetAllUserMemory() {
        SQLiteDatabase db = getWritableDatabase();
        db.delete(TABLE_USER_MEMORY, null, null);
        db.close();
    }

    // ─── User Characters ────────────────────────────────────────

    public void saveCharacter(JSONObject character) {
        SQLiteDatabase db = getWritableDatabase();
        ContentValues cv = new ContentValues();
        try {
            cv.put("id", character.getString("id"));
            cv.put("name", character.optString("name", ""));
            cv.put("age", character.optInt("age", 0));
            cv.put("role", character.optString("role", ""));
            cv.put("category", character.optString("category", ""));
            cv.put("avatar", character.optString("avatar", "💬"));
            cv.put("description", character.optString("description", ""));
            cv.put("tags", character.optJSONArray("tags") != null ?
                    character.getJSONArray("tags").toString() : "[]");
            cv.put("is_adult", character.optBoolean("is_adult") ? 1 : 0);
            cv.put("essence", character.optString("essence", ""));
            cv.put("personality", character.optString("personality", ""));
            cv.put("speaking_style", character.optString("speaking_style", ""));
            cv.put("backstory", character.optString("backstory", ""));
            cv.put("hobbies", character.optJSONArray("hobbies") != null ?
                    character.getJSONArray("hobbies").toString() : "[]");
            cv.put("system_prompt", character.optString("system_prompt", ""));
            db.insertWithOnConflict(TABLE_USER_CHARACTERS, null, cv, SQLiteDatabase.CONFLICT_REPLACE);
        } catch (Exception ignored) {}
        db.close();
    }

    public void deleteCharacter(String charId) {
        SQLiteDatabase db = getWritableDatabase();
        db.delete(TABLE_USER_CHARACTERS, "id=?", new String[]{charId});
        db.close();
    }

    public void clearMessages(String characterId) {
        SQLiteDatabase db = getWritableDatabase();
        db.delete(TABLE_MESSAGES, "character_id=?", new String[]{characterId});
        db.close();
    }

    public JSONArray getAllUserCharacters() {
        SQLiteDatabase db = getReadableDatabase();
        JSONArray arr = new JSONArray();
        Cursor c = db.rawQuery("SELECT * FROM " + TABLE_USER_CHARACTERS + " ORDER BY created_at DESC", null);
        while (c.moveToNext()) {
            try {
                JSONObject obj = new JSONObject();
                obj.put("id", c.getString(c.getColumnIndexOrThrow("id")));
                obj.put("name", c.getString(c.getColumnIndexOrThrow("name")));
                obj.put("age", c.getInt(c.getColumnIndexOrThrow("age")));
                obj.put("role", c.getString(c.getColumnIndexOrThrow("role")));
                obj.put("category", c.getString(c.getColumnIndexOrThrow("category")));
                obj.put("avatar", c.getString(c.getColumnIndexOrThrow("avatar")));
                obj.put("description", c.getString(c.getColumnIndexOrThrow("description")));
                obj.put("tags", new JSONArray(c.getString(c.getColumnIndexOrThrow("tags"))));
                obj.put("is_adult", c.getInt(c.getColumnIndexOrThrow("is_adult")) == 1);
                obj.put("essence", c.getString(c.getColumnIndexOrThrow("essence")));
                obj.put("personality", c.getString(c.getColumnIndexOrThrow("personality")));
                obj.put("speaking_style", c.getString(c.getColumnIndexOrThrow("speaking_style")));
                obj.put("backstory", c.getString(c.getColumnIndexOrThrow("backstory")));
                obj.put("hobbies", new JSONArray(c.getString(c.getColumnIndexOrThrow("hobbies"))));
                obj.put("system_prompt", c.getString(c.getColumnIndexOrThrow("system_prompt")));
                obj.put("user_created", true);
                arr.put(obj);
            } catch (Exception ignored) {}
        }
        c.close();
        db.close();
        return arr;
    }

    public boolean hasCharacter(String charId) {
        SQLiteDatabase db = getReadableDatabase();
        Cursor c = db.rawQuery(
                "SELECT 1 FROM " + TABLE_USER_CHARACTERS + " WHERE id=?",
                new String[]{charId});
        boolean exists = c.moveToFirst();
        c.close();
        db.close();
        return exists;
    }

    // ─── Evolution ──────────────────────────────────────────────

    public void saveEvolution(JSONObject evo) {
        SQLiteDatabase db = getWritableDatabase();
        ContentValues cv = new ContentValues();
        try {
            cv.put("user_id", evo.getString("user_id"));
            cv.put("character_id", evo.getString("character_id"));
            cv.put("current_stage", evo.optString("current_stage", "base"));
            cv.put("unlocked_stages", evo.optJSONArray("unlocked_stages") != null ?
                    evo.getJSONArray("unlocked_stages").toString() : "[\"base\"]");
            cv.put("flags", evo.optJSONObject("flags") != null ?
                    evo.getJSONObject("flags").toString() : "{}");
            cv.put("trait_modifiers", evo.optJSONObject("trait_modifiers") != null ?
                    evo.getJSONObject("trait_modifiers").toString() : "{}");
            cv.put("intimacy_peak", evo.optDouble("intimacy_peak", 0));
            cv.put("total_messages", evo.optInt("total_messages", 0));
            db.insertWithOnConflict(TABLE_EVOLUTION, null, cv, SQLiteDatabase.CONFLICT_REPLACE);
        } catch (Exception ignored) {}
        db.close();
    }

    public JSONObject getEvolution(String userId, String characterId) {
        SQLiteDatabase db = getReadableDatabase();
        Cursor c = db.rawQuery(
                "SELECT * FROM " + TABLE_EVOLUTION + " WHERE user_id=? AND character_id=?",
                new String[]{userId, characterId});
        JSONObject evo = null;
        if (c.moveToFirst()) {
            try {
                evo = new JSONObject();
                evo.put("user_id", c.getString(c.getColumnIndexOrThrow("user_id")));
                evo.put("character_id", c.getString(c.getColumnIndexOrThrow("character_id")));
                evo.put("current_stage", c.getString(c.getColumnIndexOrThrow("current_stage")));
                evo.put("unlocked_stages", new JSONArray(c.getString(c.getColumnIndexOrThrow("unlocked_stages"))));
                evo.put("flags", new JSONObject(c.getString(c.getColumnIndexOrThrow("flags"))));
                evo.put("trait_modifiers", new JSONObject(c.getString(c.getColumnIndexOrThrow("trait_modifiers"))));
                evo.put("intimacy_peak", c.getDouble(c.getColumnIndexOrThrow("intimacy_peak")));
                evo.put("total_messages", c.getInt(c.getColumnIndexOrThrow("total_messages")));
            } catch (Exception ignored) {}
        }
        c.close();
        db.close();
        return evo;
    }

    public void deleteEvolution(String userId, String characterId) {
        SQLiteDatabase db = getWritableDatabase();
        db.delete(TABLE_EVOLUTION, "user_id=? AND character_id=?",
                new String[]{userId, characterId});
        db.close();
    }

    // ─── Favorites ─────────────────────────────────────────────

    public void addFavorite(String characterId) {
        SQLiteDatabase db = getWritableDatabase();
        ContentValues cv = new ContentValues();
        cv.put("character_id", characterId);
        db.insertWithOnConflict(TABLE_FAVORITES, null, cv, SQLiteDatabase.CONFLICT_IGNORE);
        ContentValues histCv = new ContentValues();
        histCv.put("character_id", characterId);
        histCv.put("action", "added");
        db.insert(TABLE_FAVORITE_HISTORY, null, histCv);
        db.close();
    }

    public void removeFavorite(String characterId) {
        SQLiteDatabase db = getWritableDatabase();
        int removed = db.delete(TABLE_FAVORITES, "character_id=?", new String[]{characterId});
        if (removed > 0) {
            ContentValues histCv = new ContentValues();
            histCv.put("character_id", characterId);
            histCv.put("action", "removed");
            db.insert(TABLE_FAVORITE_HISTORY, null, histCv);
        }
        db.close();
    }

    public boolean isFavorite(String characterId) {
        SQLiteDatabase db = getReadableDatabase();
        Cursor c = db.rawQuery(
                "SELECT 1 FROM " + TABLE_FAVORITES + " WHERE character_id=?",
                new String[]{characterId});
        boolean exists = c.moveToFirst();
        c.close();
        db.close();
        return exists;
    }

    public List<String> getAllFavoriteIds() {
        List<String> ids = new ArrayList<>();
        SQLiteDatabase db = getReadableDatabase();
        Cursor c = db.rawQuery("SELECT character_id FROM " + TABLE_FAVORITES, null);
        while (c.moveToNext()) {
            ids.add(c.getString(0));
        }
        c.close();
        db.close();
        return ids;
    }

    public boolean wasRecentlyRemovedFromFavorites(String characterId, int hours) {
        SQLiteDatabase db = getReadableDatabase();
        long cutoff = System.currentTimeMillis() / 1000 - (hours * 3600L);
        Cursor c = db.rawQuery(
                "SELECT 1 FROM " + TABLE_FAVORITE_HISTORY +
                        " WHERE character_id=? AND action='removed' AND created_at > ?" +
                        " ORDER BY created_at DESC LIMIT 1",
                new String[]{characterId, String.valueOf(cutoff)});
        boolean exists = c.moveToFirst();
        c.close();
        db.close();
        return exists;
    }

    // ─── Reset All ──────────────────────────────────────────────

    public void resetAll() {
        SQLiteDatabase db = getWritableDatabase();
        db.delete(TABLE_MESSAGES, null, null);
        db.delete(TABLE_USER_MEMORY, null, null);
        db.delete(TABLE_USER_CHARACTERS, null, null);
        db.delete(TABLE_EVOLUTION, null, null);
        db.delete(TABLE_FAVORITES, null, null);
        db.delete(TABLE_FAVORITE_HISTORY, null, null);
    }
}
