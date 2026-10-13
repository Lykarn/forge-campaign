# Gate A test: Foundation

**What this gate proves:** our own build, made by CI from pinned upstream commits, opens Forge's Adventure on the `Campaign` plane and plays its duels on Neo Forge's table on Windows.

CI already checks the parts it can without a screen: the cards load, the plane and our shadowed `Config` are in the package, and (when the runner can open a window) a self-test duel runs. This test covers what only a real Windows machine shows.

## Get the build

While Actions is locked, the build is made on your machine: unzip `_build\out\ForgeCampaign-windows-x64.zip` from the repo folder somewhere you can write to (not Program Files). It is the same zip CI would upload.

Once Actions works again: open the pull request for this gate and click the green check, or go to **Actions > Windows build** and open the latest run for the branch. Under **Artifacts**, download **ForgeCampaign-windows-x64**, unzip it, and unzip the inner zip too.

If your antivirus quarantines `ForgeCampaign.exe` (Surfshark did, as `Drop.Win64.UserProfileSelfRun`, before the build stopped relaunching its own exe for the Adventure), say so on the pull request rather than adding an exclusion: it means the fix is incomplete.

## Test (about 10 minutes)

1. Run `ForgeCampaign\ForgeCampaign.exe`. Windows SmartScreen may warn about an unsigned app: **More info > Run anyway**.
2. Wait for the menu (the first launch reads every card, about a minute). Open **Adventure**.
3. Start a new game with any difficulty and starter deck.
4. Walk into any enemy on the map to start a duel.
5. Check that the duel uses Neo Forge's modern table (drag cards to cast, curved attack arrows), not Forge's older screen.
6. Play or concede the duel and check you return to the map.

## Report

Reply on the pull request with:

- **Pass or fail** for steps 2, 5 and 6.
- Anything that looked broken or slow.
- If something failed: attach `ForgeCampaign\data\neo\neo.log` and `ForgeCampaign\data\neo\adventure.log`.

Merging the pull request is your sign-off that Gate A passed.
