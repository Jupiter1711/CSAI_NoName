from bloxorz.core.problem import BloxorzProblem

from .base import SearchResult


def reconstruct_path(came_from: dict, state) -> list[str]:
    path = []
    while came_from.get(state) is not None:
        state, action = came_from[state]
        path.append(action)
    path.reverse()
    return path


def solve(problem: BloxorzProblem) -> SearchResult:
    start_state = problem.initial_state()
    stack = [start_state]

    came_from = {start_state: None}
    expanded = 0

    while stack:
        state = stack.pop()

        if problem.is_goal(state):
            path = reconstruct_path(came_from, state)
            return SearchResult(path=path, expanded=expanded, cost=float(len(path)))

        expanded += 1

        for action, next_state, cost in problem.successors(state):
            if next_state not in came_from:
                came_from[next_state] = (state, action)
                stack.append(next_state)

    return SearchResult(path=None, expanded=expanded, cost=0.0)
