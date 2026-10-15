package forge.campaign.cards;

import forge.ImageKeys;
import forge.StaticData;
import forge.adventure.util.Config;
import forge.card.CardDb;
import forge.card.CardEdition;
import forge.card.CardRarity;
import forge.card.CardRules;
import forge.item.PaperCard;
import forge.util.FileUtil;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * Adventure's custom cards (res/adventure/common/custom_cards: item and boss effects, and our
 * relics, campaign_*.txt) for headless tools. The game registers them in Config.loadResources(),
 * which TierBench never calls; this does the same, card by card, and skips cards already there.
 */
public final class CustomCards {
    private static boolean loaded;

    private CustomCards() {
    }

    /** Registers every custom card once; returns the names of the cards it added. */
    public static synchronized List<String> load() {
        List<String> added = new ArrayList<>();
        if (loaded) {
            return added;
        }
        loaded = true;
        ImageKeys.ADVENTURE_CARD_PICS_DIR = Config.instance().getCommonFilePath(forge.adventure.util.Paths.CUSTOM_CARDS_PICS);
        File[] files = new File(Config.instance().getCommonFilePath(forge.adventure.util.Paths.CUSTOM_CARDS)).listFiles();
        if (files == null) {
            return added;
        }
        CardRules.Reader reader = new CardRules.Reader();
        for (File file : files) {
            try (InputStreamReader in = new InputStreamReader(new FileInputStream(file), StandardCharsets.UTF_8)) {
                reader.reset();
                List<String> lines = FileUtil.readAllLines(in, true);
                CardRules rules = reader.readCard(lines, com.google.common.io.Files.getNameWithoutExtension(file.getName()));
                rules.setCustom();
                CardDb db = rules.isVariant() ? StaticData.instance().getVariantCards() : StaticData.instance().getCommonCards();
                if (db.getCard(rules.getName()) != null) {
                    continue;
                }
                db.addCard(new PaperCard(rules, CardEdition.UNKNOWN_CODE, CardRarity.Special) {
                    @Override
                    public String getImageKey(boolean altState) {
                        return ImageKeys.ADVENTURECARD_PREFIX + getName();
                    }
                });
                added.add(rules.getName());
            } catch (IOException | RuntimeException e) {
                System.err.println("[campaign] custom card " + file.getName() + ": " + e);
            }
        }
        return added;
    }
}
