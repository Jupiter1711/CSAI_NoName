from .base import SearchResult
from bloxorz.core.rules import initial_state, is_goal, actions, step 

def reconstruct_path(came_from: dict, state) -> list[str]:
    path = []
    while came_from.get(state) is not None:
        state, action = came_from[state]
        path.append(action)
    path.reverse()
    return path

def solve(level) -> SearchResult:
    start_state = initial_state(level)
    stack = [start_state]
    
    came_from = {start_state: None}
    expanded = 0
    
    while stack:
        state = stack.pop()
        
        if is_goal(level, state):
            path = reconstruct_path(came_from, state)
            return SearchResult(path=path, expanded=expanded)
            
        expanded += 1
        
        for action in actions(state):
            next_state = step(level, state, action)
            
            if next_state is not None:
                if next_state not in came_from:
                    came_from[next_state] = (state, action)
                    stack.append(next_state)
                
    return SearchResult(path=None, expanded=expanded)