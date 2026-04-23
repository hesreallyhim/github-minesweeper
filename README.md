# GitHub Issue Minesweeper

This repository is the public gameplay surface for GitHub-native Minesweeper.

## Start A Room

1. Go to **Issues** -> **New issue**.
2. Choose **Minesweeper Room**.
3. Submit the issue and play in comments.

## Command Format

Use plain commands (slash prefix is also accepted):

- `A1 B2` or `guess A1 A2` - reveal cell(s)
- `flag H7 H8` - flag suspected mine(s)
- `unflag H7` - remove flag(s)
- `giveup` - end the game

Rules:

- Commands are case-insensitive.
- Use one action per line.
- Any unrecognized token invalidates the whole turn.

## Hall Of Fame

<!-- MS_LEADERBOARD_START -->
### Leaderboards
_As of (UTC): 2026-04-21T05:07:54+00:00 from 2 completed games_
(Leaderboards update every 15 minutes)

<table align="center">
  <tr>
    <td><picture><img src="assets/readme-leaderboard-card-champions.svg" alt="Champions Card" width="460" /></picture></td>
    <td><picture><img src="assets/readme-leaderboard-card-commitment.svg" alt="Commitment Card" width="460" /></picture></td>
  </tr>
  <tr>
    <td><picture><img src="assets/readme-leaderboard-card-quick-clear.svg" alt="Quick Clear Card" width="460" /></picture></td>
    <td><picture><img src="assets/readme-leaderboard-card-consistency.svg" alt="Consistency Card" width="460" /></picture></td>
  </tr>
</table>
<!-- MS_LEADERBOARD_END -->

## Repository Surface

- `.github/ISSUE_TEMPLATE/` - room creation UX
- `.github/workflows/minesweeper-leaderboards.yml` - scheduled leaderboard publishing
- `scripts/build_leaderboards.py` - leaderboard build entrypoint
- `src/minesweeper/leaderboards.py` - leaderboard logic and README block rendering
- `data/games/` - terminal game records
- `data/leaderboards.json` - machine-readable leaderboard summary
- `assets/readme-leaderboard-card-*.svg` - generated leaderboard cards
