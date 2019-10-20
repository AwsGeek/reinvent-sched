import os
import json
import math
import random
import datetime

traveltime = 60
venuetime = 5
def does_conflict(x,y):
    
    commute = venuetime * 60
    if x['venue'] != y['venue']:
        commute = traveltime * 60
    
    xbeg = x['timestamp']
    xend =  x['timestamp'] + x['duration'] + commute
    ybeg = y['timestamp']
    yend =  y['timestamp'] + y['duration'] + commute
    
    return bool((ybeg <= xbeg <= yend) or (xbeg <= ybeg <= xend) or (xbeg <= ybeg and xend >= yend) or (ybeg <= xbeg and yend >= xend))


def get_conflicts(sessions):
    # Find all conflicts (and chains of conflicts)

    if len(sessions) == 0:
        return [], []
        
    if len(sessions) == 1:
        return sessions, []
    
    
    conflicts = []
    unconflicted = []
    
    previous = sessions[0]
    temp = [previous]
    selected = []
    
    for current in sessions[1:]:

        is_conflict = does_conflict(previous, current)
        if not is_conflict:

            # Not a conflict
            if len(temp) > 1:
                conflicts.append(temp)
            else:
                for i in temp:
                    if i['code'] not in selected:
                        unconflicted.append(i)
                        selected.append(i['code'])
                        
            temp = []
            
        if current['timestamp'] + current['duration'] >= previous['timestamp'] + previous['duration']:
            previous = current
            
        temp.append(current)

        if current == sessions[-1] and not is_conflict:
            if current['code'] not in selected:
                unconflicted.append(current)
                selected.append(current['code'])
            
    if len(temp) > 1:
        conflicts.append(temp)
    
    return unconflicted, conflicts

# Count the number of venuer changes each day and return the sum of all. 
def num_commutes(sessions):
    
    commutes = 0
    if len(sessions) <= 1:
        return 0
        
    sessions.sort(key=lambda x: x['timestamp'], reverse=False)
    previous = sessions[0]
    for current in sessions[1:]:
        if current['day'] == previous['day'] and current['venue'] != previous['venue']:
            commutes += 1
        previous = current
        
    return commutes

# Choose the session with the highest priority. If there 
# are multiple with the same priority, randomly choose one
def choose_session(sessions):
    
    sessions.sort(key=lambda x: x['priority'], reverse=True)
    
    priority = sessions[0]['priority']
    subset = [x for x in sessions if x['priority'] == priority]
    
    return random.choice(subset)
    

def handler(master, context):
    
    # Sort by date in ascending order
    master.sort(key=lambda x: x['timestamp'], reverse=False)

    best = []
    if master:

        notimproved = 0;
        
        unconflicted, conflicts = get_conflicts(master)
        miniterations = 10 * len(conflicts)
        
        for y in range(0, max(1,math.factorial(len(conflicts)))):

            if notimproved > miniterations:
                break
            
            sessions = master.copy()
            schedule = []
            
            unconflicted, conflicts = get_conflicts(sessions)
            while len(conflicts):
                
                for session in unconflicted:
                    duplicates = [x for x in sessions if x['code'] == session['code']]
                    for dup in duplicates:
                        if dup['key'] != session['key']:
                            sessions.remove(dup)
                        
                unconflicted, conflicts = get_conflicts(sessions)
                for conflict in conflicts:
                    # Pick one, add it the schedule, remove all those that conflict with it (not all will)
                    c = choose_session(conflict)
                    
                    unconflicted.append(c)
                    for x in conflict:
                        if x != c and does_conflict(x,c):
                            sessions.remove(x)

                unconflicted, conflicts = get_conflicts(sessions)
                
            if len(unconflicted) == len(best):
                if num_commutes(unconflicted) < num_commutes(best):
                    best = unconflicted
                    notimproved = 0
                else:
                    notimproved += 1
            elif len(unconflicted) > len(best):
                best = unconflicted
                notimproved = 0
            else:
                notimproved += 1

    return best