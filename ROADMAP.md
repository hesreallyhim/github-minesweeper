# ROADMAP

## Purpose

Track the implementation of the GitHub-native issue-room Minesweeper repo.

## Phase 0: Planning Freeze

Goal:
- lock the v1 product direction and mechanics before unattended execution

Done when:
- gameplay contract is documented
- implementation constraints are explicit
- linear job breakdown exists

## Phase 0.5: Target Repo Bootstrap

Goal:
- create the clean target repo shell and seed only the control plane

Expected outputs:
- repo shell exists
- control documents exist
- bootstrap development files exist
- linear factory runner exists

Gate:
- the first factory run can start without additional human setup

## Phase 1: Repo Foundation And Contracts

Goal:
- create the repository structure, package skeleton, docs shell, and rules
  contract for the game

Expected outputs:
- package layout
- tests layout
- docs layout
- issue template and workflow placeholders

Gate:
- the repo shape is coherent and ready for gameplay logic

## Phase 2: Engine And Secure State Chain

Goal:
- implement Minesweeper rules, command parsing, state transitions, and hidden
  signed state integrity

Expected outputs:
- core engine
- coordinate parser
- state encoder/decoder
- owner and replay guards
- deterministic tests

Gate:
- local tests can prove valid state transitions without GitHub access

## Phase 3: GitHub Issue Orchestration

Goal:
- implement issue creation, comment command handling, room ownership, and bot
  response flow

Expected outputs:
- issue templates
- workflow entrypoints
- event normalization layer
- comment response rendering pipeline

Gate:
- fixtures can replay issue/comment events and produce correct outputs

## Phase 4: Rendering And Player Feedback

Goal:
- make the room feel legible and satisfying inside GitHub issue comments

Expected outputs:
- board renderer
- room status renderer
- win/loss messaging
- optional lightweight leaderboard or hall-of-fame output

Gate:
- the comment UX is understandable without reading source code

## Phase 5: Docker Simulation And Launch Polish

Goal:
- make local development and unattended verification practical in Docker

Expected outputs:
- Dockerfile and local compose path or equivalent docker run story
- replay fixtures
- make targets for simulation and tests
- launch checklist and operator docs

Gate:
- a developer can validate the main files and game loop locally without live
  GitHub workflow end-to-end validation

## Non-Goals For This Sequence

- multi-player rooms
- external database infrastructure
- web frontend outside GitHub issue comments
- real-time networking
- mandatory live GitHub workflow integration testing
