"""Shared memory (plan section 7): SQLite state store with typed messages and a task queue."""
import json
import sqlite3
import threading
import time
from collections import deque
from triage.team.schemas import Message

class StateStore:
    def __init__(self,path=':memory:'):
        self.lock=threading.Lock()
        self.db=sqlite3.connect(str(path),check_same_thread=False)
        self.db.execute('create table if not exists messages(seq integer primary key autoincrement,incident_id text,sender text,recipient text,type text,status text,payload text,ts real)')
        self.db.execute('create table if not exists conclusions(incident_id text,method text,conclusion text,ts real)')

    def post(self,**kwargs):
        m=Message(**kwargs)
        with self.lock:
            self.db.execute('insert into messages(incident_id,sender,recipient,type,status,payload,ts) values(?,?,?,?,?,?,?)',(m.incident_id,m.sender,m.recipient,m.type,m.status,json.dumps(m.payload,ensure_ascii=False),time.time()))
            self.db.commit()
        return m

    def read(self,incident_id,sender=None,type=None):
        sql='select sender,recipient,type,status,payload from messages where incident_id=?';args=[incident_id]
        if sender:sql+=' and sender=?';args.append(sender)
        if type:sql+=' and type=?';args.append(type)
        with self.lock:rows=self.db.execute(sql+' order by seq',args).fetchall()
        return [{'sender':s,'recipient':r,'type':t,'status':st,'payload':json.loads(p)} for s,r,t,st,p in rows]

    def write_conclusion(self,incident_id,method,conclusion):
        with self.lock:
            self.db.execute('insert into conclusions values(?,?,?,?)',(incident_id,method,json.dumps(conclusion,ensure_ascii=False),time.time()));self.db.commit()

class TaskQueue:
    def __init__(self):self.items=deque()
    def push(self,task):self.items.append(task)
    def drain(self):
        out=list(self.items);self.items.clear();return out
