# Privacy

In order to make the game reasonably enjoyable, gameplay interactions
are handled via a webhook which communicates with a small endpoint
hosted on Cloudflare. (For more information on why webhooks are utilized
instead of GitHub Actions, please consult the repository's Wiki - basically,
the reason is just that using GitHub Actions workflows would add a few seconds
or more of waiting time between moves, which can seriously degrade the user's
enjoyment of the game.)

Data sent to the Cloudflare worker endpoint include metadata about the game, the
action/comment just submitted, the username who makes any comment, the username of
the issue's owner, and some data about the game state. This data is not persisted
or analyzed for any significant amount of time, only that which is needed for the purposes
of moderation, or defense against excessive activity. The data is not transferred or sold
to any other parties and is not used for any other purpose. User's gameplay statistics
(number of games played, won, date of play, etc.), is stored on a longer-term basis
in order to populate the game's leaderboards, but does not involve any personal or
non-public information.

Because it is intended to be a pristine, public gameplay "UI" surface, the `main` branch
has been stripped of all non-essential code. However, if you wish to inspect the
code that is deployed to Cloudflare, the full source code resides on the
`develop` branch.
