package forge.campaign.enemies;

import com.badlogic.gdx.files.FileHandle;
import com.badlogic.gdx.utils.Json;
import com.badlogic.gdx.utils.JsonReader;
import com.badlogic.gdx.utils.JsonValue;
import forge.adventure.data.EffectData;
import forge.adventure.data.EnemyData;
import forge.adventure.util.Config;

import java.util.HashMap;
import java.util.Map;

/**
 * What an enemy brings to every duel, wherever it is met (plane/world/enemy_effects.json).
 *
 * Adventure gives an enemy effects only through the map it stands on (a Tiled "effect" or a
 * dungeon's "dungeonEffect") or through its equipment, which upstream applies in events only. A
 * roaming champion or a planeswalker boss needs its effect in every duel, so our DuelScene adds
 * this one for map duels, and TierBench adds it too so the benchmark plays the same fight.
 *
 * Format: { "Enemy name": { "effect": { EffectData }, "takesPower9": true } }; keys starting
 * with "_" are notes. "effect" is Adventure's own EffectData (startBattleWithCard,
 * startBattleWithCardInCommandZone, lifeModifier, changeStartCards, opponent).
 */
public final class EnemyEffects {
    public static final String FILE = "world/enemy_effects.json";

    /** One enemy's entry. */
    public static final class Entry {
        public EffectData effect;
        /** The Oracle of the Alpha: the player's Power 9 play for him in this duel (PowerNine). */
        public boolean takesPower9;
    }

    private static volatile Map<String, Entry> entries;

    private EnemyEffects() {
    }

    public static Entry of(EnemyData enemy) {
        return enemy == null ? null : all().get(enemy.name);
    }

    public static EffectData effectOf(EnemyData enemy) {
        Entry e = of(enemy);
        return e == null ? null : e.effect;
    }

    public static boolean takesPower9(EnemyData enemy) {
        Entry e = of(enemy);
        return e != null && e.takesPower9;
    }

    public static Map<String, Entry> all() {
        Map<String, Entry> m = entries;
        if (m == null) {
            synchronized (EnemyEffects.class) {
                if (entries == null) {
                    entries = load();
                }
                m = entries;
            }
        }
        return m;
    }

    private static Map<String, Entry> load() {
        Map<String, Entry> m = new HashMap<>();
        FileHandle file = Config.instance().getFile(FILE);
        if (file == null || !file.exists()) {
            return m;
        }
        Json json = new Json();
        json.setIgnoreUnknownFields(true);
        for (JsonValue v = new JsonReader().parse(file).child; v != null; v = v.next) {
            if (v.name != null && !v.name.startsWith("_")) {
                m.put(v.name, json.readValue(Entry.class, v));
            }
        }
        return m;
    }
}
