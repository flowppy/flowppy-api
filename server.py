from bottle import run, get, post, view, hook, response, route, request;
import os;
import plupload;
import random;
import time;
import threading;
from subprocess import Popen, PIPE, STDOUT, check_output;
import shutil;
import pexpect;
import sys;
import json;
import re;

loaded_gdbs = {};
loaded_gdbs_lock = threading.Lock();


class GDBThread(threading.Thread):
    def __init__(self, gdb):
        self.stdout = None;
        self.stderr = None;
        self.gdb = gdb;
        self.prompt = "\\(gdb\\) ";
        threading.Thread.__init__(self);
                
    def command(self, command):
        self.process.sendline(command);
        self.process.expect(self.prompt);
        result = {};
        result["output"] = self.process.before;
        result["instruction"] = self.get_current_instruction();
        return json.dumps(result);
        
    def get_current_instruction(self):
        self.process.sendline("print /$pc");
        self.process.expect(self.prompt);
        return re.search("0[xX][0-9a-fA-F]+", self.process.before).group(0);
        
    def kill(self):
        self.process.close(force=True);
        
    def run(self):
        self.process = pexpect.spawnu("gdb " + self.gdb.filepath + self.gdb.filename);
        self.process.expect(self.prompt);
        self.process.sendline("set confirm off");
        self.process.expect(self.prompt);

class GDB(object):
    
    def __init__(self, filepath, filename, identifier):
        self.filepath = filepath;
        self.filename = filename;
        self.identifier = identifier;
        self.started = False;
        self.refresh();
        print("Created #" + identifier + " (" + filename + ")");
        
        
    def command(self, command):
        return self.thread.command(command);
        
    def stop(self):
        if self.started:
            self.thread.kill();
        shutil.rmtree(self.filepath);
        print("Destroyed #" + self.identifier + " (" + self.filename + ")");

    def create_graph(self, f):
        return check_output(["./flowppy/flowppy", "-i", self.filepath + self.filename, "-t", "condensed", "-f", f]);
        
    def start_gdb(self):
        if not self.started:
            self.started = True;
            self.thread = GDBThread(self);
            self.thread.start();
            self.thread.join();
            return "OK";
        return "GDB déjà démarré";
        
    def refresh(self):
        self.time = time.time();
        
class RefreshThread(threading.Thread):
    def __init__(self, event):
        threading.Thread.__init__(self)
        self.stopped = event

    def run(self):
        while not self.stopped.wait(60):
            stop_timed_out_gdbs();
            
def stop_all_gdbs():
    for i in loaded_gdbs:
        loaded_gdbs[i].stop();
        
            
def stop_timed_out_gdbs():
    loaded_gdbs_lock.acquire();
            
    tokill = [];
    
    for i in loaded_gdbs:
        gdb = loaded_gdbs[i];
        if time.time() - gdb.time > 80:
            tokill.append(gdb);
    
    for gdb in tokill:
        gdb.stop();
        del loaded_gdbs[gdb.identifier];
    
    loaded_gdbs_lock.release();
    
allowed_commands = [("start", "Exécute ou redémarre le programme"), 
                    ("stepi", "Saute à lap rochaine instruction assembleur (éxécute les fonctions)"),
                    ("step", "Saute à la prochaine ligne de code (éxécute les fonctions)"), 
                    ("s", "Alias de step"),
                    ("continue", "Continue l'exécution jusqu'au prochain breakpoint"),
                    ("c", "Alias de continue"),
                    ("until", "Continue l'éxecution jusqu'à un certain, numéro de ligne, nom de fonction ou adresse"),
                    ("break", "Suspend le programme à une adresse donnée"), 
                    ("print", "Affiche la valeur d'un registre ou d'une variable"), 
                    ("p", "Alias de print"),
                    ("display", "A chaque nouvelle instruction, affiche la valeur d'un registre ou d'une variable"),
                    ("x", "Alias de print sous forme héxadécimale"), 
                    ("d", "Alias de print sous forme signée"),
                    ("u", "Alias de print sous forme non-signée"),
                    ("o", "Alias de print sous forme octale"),
                    ("t", "Alias de print sous forme entière"),
                    ("a", "Alias de print sous forme entière signée"),
                    ("c", "Alias de print sous forme de caractères"),
                    ("frame", "Affiche le cadre de la fonction en cours"),  
                    ("f", "Alias de frame"),
                    ("return", "Arrête l'exécution de la fonction en cours"),
                    ("finish", "Continue jusqu'à la fin de la fonction courante"), 
                    ("enable", "Active un breakpoint"), 
                    ("disable", "Désactive un breakpoint"), 
                    ("tbreak", "Pose un breakpoint temporaire"), 
                    ("where", "Montre le numéro de la ligne et la fonction courante"),
                    ("info", "Affiche les infos du cadre courant"), 
                    ("list", "Affiche le code source"), 
                    ("next", "Exécute la prochaine ligne de code (n'éxécute pas les fonctions)"),
                    ("nexti", "Alias de stepi mais (n'éxécute pas les fonctions)"),
                    ("jump", "Saute a l'adresse donnée")
];
                    
@route('/command/<identifier>/<command:path>')
def command(identifier, command):
    instruction = command.split(' ', 1)[0];
            
    if instruction not in (list(i[0] for i in allowed_commands)):
        return "Commande inconnue ou interdite.";
        
    output = "Identifiant inconnu";
        
    loaded_gdbs_lock.acquire();
    
    if identifier in loaded_gdbs:
        loaded_gdbs[identifier].refresh();
        output = loaded_gdbs[identifier].command(command);
    
    loaded_gdbs_lock.release();
    return output;
    
@route('/allowedcommands')
def allowedcommands():
    return json.dumps(list([i[0], i[1]] for i in allowed_commands));
    
@route('/startgdb/<identifier>')
def start_gdb(identifier):
    loaded_gdbs_lock.acquire();
    if identifier in loaded_gdbs:
        output = loaded_gdbs[identifier].start_gdb();
    loaded_gdbs_lock.release();
    
    return output;

@route('/refresh/<identifier>')
def refresh(identifier):
    loaded_gdbs_lock.acquire();
    
    ok = False;
    
    if identifier in loaded_gdbs:
        loaded_gdbs[identifier].refresh();
        ok = True;
    loaded_gdbs_lock.release();
    
    return "OK" if ok else "Identifiant inconnu";
    
@route('/creategraph/<identifier>/<f>')
def create_graph(identifier, f):
    loaded_gdbs_lock.acquire();
    graph = "Identifiant inconnu";
    
    if f == "png":
        response.content_type = "image/png";
    elif f == "svg":
        response.content_type = "image/svg+xml";
    elif f == "dot":
        response.content_type = "application/dot";
    elif f == "json":
        response.content_type = "application/json";
    else:
        loaded_gdbs_lock.release();
        return "Format inconnu";
    
    if identifier in loaded_gdbs:
            
        gdb = loaded_gdbs[identifier];
        gdb.refresh();
    
        graph = gdb.create_graph(f);
        
        response.set_header("Content-Disposition", "attachment; filename=" + gdb.filename + "_graph." + f);
    
    loaded_gdbs_lock.release();
    
    return graph;

@route('/upload', method=['POST', 'OPTIONS'])
def upload():
    filename = plupload.get_filename(request.forms, request.files);
    
    if not filename:
        return "";
        
    identifier = str(random.randint(0, 6845)) + filename;
    filepath = os.getcwd() + "/gdbs/" + identifier + "/";
    os.makedirs(filepath);
    
    gdb = GDB(filepath, filename, identifier);
    add_gdb(identifier, gdb);
    
    return plupload.save(request.forms, request.files, filepath, identifier);
    
def add_gdb(identifier, gdb):
    loaded_gdbs_lock.acquire();
    
    loaded_gdbs[identifier] = gdb;
    
    loaded_gdbs_lock.release();

    
@hook('after_request')
def enable_cors():
    response.headers['Access-Control-Allow-Origin'] = '*';

if __name__ == "__main__":
    if os.path.exists(os.getcwd() + "/gdbs/"):
        shutil.rmtree(os.getcwd() + "/gdbs/");
        
    stopFlag = threading.Event();
    thread = RefreshThread(stopFlag);
    thread.start();
    run(host = os.getenv("IP", "0.0.0.0"), port=os.getenv("PORT", "80"));
    stopFlag.set();
    stop_all_gdbs();
     