"""A competent but beatable opponent for the hidden terminal game."""
from functools import lru_cache
import random

LINES=((0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6))
MISTAKE_CHANCE=.132


def result(board):
    for a,b,c in LINES:
        if board[a] and board[a]==board[b]==board[c]:return board[a]
    return 'draw' if all(board) else None


@lru_cache(maxsize=10000)
def score(board,turn):
    outcome=result(board)
    if outcome:return {'O':1,'X':-1,'draw':0}[outcome]
    values=[]
    for index,mark in enumerate(board):
        if not mark:
            next_board=board[:index]+(turn,)+board[index+1:]
            values.append(score(next_board,'X' if turn=='O' else 'O'))
    return max(values) if turn=='O' else min(values)


def move_options(board):
    board=tuple(board)
    if result(board):return (),()
    available=tuple(i for i,mark in enumerate(board) if not mark)
    winning=tuple(i for i in available if result(board[:i]+('O',)+board[i+1:])=='O')
    if winning:return winning,winning
    values={i:score(board[:i]+('O',)+board[i+1:],'X') for i in available}
    best=max(values.values())
    return available,tuple(i for i in available if values[i]==best)


def choose_move(board,rng=random):
    available,best=move_options(board)
    if not available:return None
    # Finish a winning line reliably. Otherwise play strategically, with an
    # occasional lapse that a player can turn into a win.
    return rng.choice(available if rng.random()<MISTAKE_CHANCE else best)
