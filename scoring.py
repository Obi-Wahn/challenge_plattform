"""Shared ranking logic for the scoreboard, the award ceremony and the certificates."""

from models import Task, Team, Submission


def get_standings(challenge):
    """Returns (tasks, standings) for a challenge, best team first.

    Only teams registered for this competition are included, each of them even
    without a submission. Teams on the
    same total share a rank and the next team moves up rather than the rank
    being skipped (1, 2, 2, 3), so a tie never leaves a place on the podium
    empty and a tie is never resolved arbitrarily.
    """
    tasks = Task.query.filter_by(challenge_id=challenge.id).order_by(Task.id).all()
    teams = Team.query.filter_by(challenge_id=challenge.id).order_by(Team.name).all()
    submissions = Submission.query.join(Task).filter(Task.challenge_id == challenge.id).all()

    standings = {
        team.id: {
            "team_id": team.id,
            "name": team.name,
            # Nur die vom Admin freigegebenen Namen - die Urkunde ist die
            # einzige Stelle, die sie zeigt.
            "members": team.certificate_names,
            "task_points": {task.id: 0 for task in tasks},
            "solved": 0,
            "total": 0,
        }
        for team in teams
    }

    for submission in submissions:
        entry = standings.get(submission.team_id)
        if entry is None:
            continue
        points = submission.points or 0
        entry["task_points"][submission.task_id] = points
        entry["total"] += points
        entry["solved"] += 1

    ordered = sorted(standings.values(), key=lambda e: (-e["total"], e["name"].lower()))

    rank = 0
    previous_total = None
    for entry in ordered:
        if entry["total"] != previous_total:
            rank += 1
            previous_total = entry["total"]
        entry["rank"] = rank

    return tasks, ordered


def get_podium(standings, places=3):
    """Returns the entries on the first `places` ranks, grouped per rank.

    Ties are kept together, so a rank can hold more than one team.
    """
    podium = []
    for place in range(1, places + 1):
        teams = [entry for entry in standings if entry["rank"] == place and entry["total"] > 0]
        if teams:
            podium.append({"place": place, "teams": teams})
    return podium
