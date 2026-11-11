"""Sound effects, NPC voices and music - D2's own, read from the player's MPQs (d2sfx, d2speech,
d2xtalk, d2music, d2xmusic) through D2's tables:

  Sounds.txt         every sound: file, volume, random variants (Group Size), looping
  SoundEnviron.txt   each area's song and ambience (Levels.txt SoundEnv)
  MonSounds.txt      monster attack / get-hit / death sounds (MonStats MonSound)
  Skills.txt         skill sounds (stsound / dosound), Missiles.txt travel / hit sounds
  Armor/Weapons/Misc drop and use (pick up) sounds of items

D2's wav files are Huffman + ADPCM packed. Unpacking that in Python is slow, so a background
process does it (and the MPQ cache keeps the result): the first time a sound is needed it can be
a moment late, after that it is instant. Music is written to cache\\music as plain .wav and streamed.
"""
import io
import os
import random
import time

import pygame

SFX_DIRS = ("data\\global\\sfx\\", "data\\local\\sfx\\")
MUSIC_DIR = "data\\global\\music\\"
CLASS_SND = {"ama": "amazon", "sor": "sorceress", "nec": "necromancer", "pal": "paladin", "bar": "barbarian",
             "dru": "druid", "ass": "assassin"}
# weapon class -> swing sound / what it sounds like when it lands
SWING = {"1hs": "weapon_1hs_large", "2hs": "weapon_2hs_large", "1ht": "weapon_1ht", "2ht": "weapon_2ht",
         "stf": "weapon_staff", "bow": "weapon_bow", "xbw": "weapon_xbow", "hth": "weapon_punch",
         "ht1": "weapon_1hs_small", "ht2": "weapon_1hs_small", "1js": "weapon_1hs_small", "1jt": "weapon_1ht",
         "1ss": "weapon_1hs_small", "1st": "weapon_1ht"}
IMPACT = {"1hs": "impact_blade_swing", "2hs": "impact_blade_swing", "1ht": "impact_blade_thrust",
          "2ht": "impact_blade_thrust", "stf": "impact_blunt", "bow": "impact_arrow", "xbw": "impact_arrow",
          "hth": "impact_punch", "ht1": "impact_claw", "ht2": "impact_claw"}
PRELOAD = ["cursor_button_click", "cursor_select", "cursor_pass", "cursor_switch", "cursor_level_up",
           "cursor_questdone", "item_flippy", "item_gold", "item_potion", "item_potion_drink",
           "impact_blade_swing", "impact_blunt", "impact_arrow", "impact_punch", "impact_blade_thrust",
           "weapon_1hs_large", "weapon_2hs_large", "weapon_1ht", "weapon_2ht", "weapon_staff", "weapon_bow",
           "weapon_punch", "weapon_kick", "player_townportal_cast", "player_townportal_enter",
           "object_chest_small", "object_wood_break", "object_urn_break", "object_door_wood_open",
           "object_waypoint_open"]

SOUND = None          # the game's SoundSystem (None: no sound)


def _int(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


class SoundSystem:
    def __init__(self, assets, opts=None):
        self.ok = False
        self.opts = opts or {}
        self.src = getattr(assets, "src", None)
        if self.src is None:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(44100, -16, 2, 1024)
            pygame.mixer.set_num_channels(32)
            pygame.mixer.set_reserved(2)          # 0: NPC voices, 1: ambience
        except Exception as e:
            print("  no sound:", e)
            return
        from d2.source import read_table
        try:
            rows = read_table(self.src, "Sounds")
        except Exception as e:
            print("  no Sounds.txt:", e)
            return
        self.rows = rows
        self.by_name = {}
        self.by_index = {}
        for i, r in enumerate(rows):
            n = r.get("sound", "")
            if n:
                self.by_name[n] = i
                self.by_index[_int(r.get("index"), i)] = n
        self.cache_root = getattr(assets, "cache_root", None) or os.path.join(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))), "cache")
        self.music_dir = os.path.join(self.cache_root, "music")
        try:
            os.makedirs(self.music_dir, exist_ok=True)
        except OSError:
            pass
        self.loaded = {}          # path -> pygame Sound (None: could not load)
        self.pending = set()
        self.voice_want = None    # (path, since)
        self.music_want = None    # sound name
        self.music_now = None
        self.ambient_now = None
        self.last = {}            # name -> time it last played (no machine-gun repeats)
        self.failed = set()
        self.late = []            # sounds asked for while still being unpacked: played if ready in time
        self._warmed = set()
        self._tables(read_table)
        self._start_worker(assets)
        self.ok = True
        for n in PRELOAD:
            for path in self._variants(n):
                self.request(path)

    # ------------------------------------------------------------ D2 tables
    def _tables(self, read_table):
        def rows(name):
            try:
                return read_table(self.src, name)
            except Exception:
                return []
        self.env_song = {}
        self.env_amb = {}
        for r in rows("SoundEnviron"):
            i = _int(r.get("index"), -1)
            self.env_song[i] = self.by_index.get(_int(r.get("song")))
            self.env_amb[i] = self.by_index.get(_int(r.get("day ambience")))
        self.level_env = {_int(r.get("id"), -1): _int(r.get("soundenv")) for r in rows("Levels")}
        self.monsound = {r.get("id", ""): r for r in rows("MonSounds") if r.get("id")}
        self.mon_snd_id = {}
        for r in rows("MonStats"):
            self.mon_snd_id[(r.get("id") or "").lower()] = r.get("monsound", "")
        self.state_snd = {r.get("state", ""): r.get("onsound") or "" for r in rows("States") if r.get("state")}
        self.skill_snd = {}
        self.skill_row = {}
        for r in rows("Skills"):
            n = r.get("skill", "")
            if n:
                self.skill_snd[n] = (r.get("stsound") or r.get("stsoundclass") or "", r.get("dosound") or "")
                self.skill_row[n] = r
        self.missile_snd = {}
        for r in rows("Missiles"):
            n = (r.get("missile") or "").lower()
            if n:
                self.missile_snd[n] = (r.get("travelsound") or "", r.get("hitsound") or "")
        self.item_snd = {}
        for t in ("Armor", "Weapons", "Misc"):
            for r in rows(t):
                c = r.get("code", "")
                if c:
                    self.item_snd[c] = (r.get("dropsound") or "", r.get("usesound") or "")

    def _variants(self, name):
        """Sound name -> its files (D2 picks one of Group Size rows at random)."""
        i = self.by_name.get(name)
        if i is None:
            i = self.by_name.get(name + "_1")
            if i is None:
                return []
        r = self.rows[i]
        g = max(1, _int(r.get("group size"), 0))
        out = []
        for k in range(i, min(len(self.rows), i + g)):
            f = (self.rows[k].get("filename") or "").strip()
            if f and f.lower() != "none.wav":
                out.append(self._path(self.rows[k].get("sound", ""), f))
        return [p for p in out if p]

    def _path(self, name, f):
        if name.startswith("music_"):
            return MUSIC_DIR + f
        for d in SFX_DIRS:
            if self.src.has(d + f):
                return d + f
        return None

    def _row(self, name):
        i = self.by_name.get(name)
        if i is None:
            i = self.by_name.get(name + "_1")
        return self.rows[i] if i is not None else {}

    # ------------------------------------------------------------ loading
    def _sweep_lists(self):
        """Every sound file of the game, most likely first: (music + speech, sound effects)."""
        music, speech, sfx = [], [], []
        first = ("cursor\\", "item\\", "combat\\", "object\\", "skill\\", "misc\\")
        seen = set()
        for r in self.rows:
            f = (r.get("filename") or "").strip()
            n = r.get("sound", "")
            if not f or f.lower() == "none.wav":
                continue
            path = self._path(n, f)
            if not path or path in seen:
                continue
            seen.add(path)
            if path.startswith(MUSIC_DIR):
                music.append(path)
            elif path.startswith(SFX_DIRS[1]):
                speech.append(path)
            else:
                sfx.append(path)
        sfx.sort(key=lambda q: (0 if q[len(SFX_DIRS[0]):].lower().startswith(first) else 1))
        music.sort(key=lambda q: (0 if ("town" in q.lower() or "wild" in q.lower()) else 1))
        return music + speech, sfx

    def _start_worker(self, assets):
        """Two unpackers: one for music and voices (you hear them start), one for sound effects."""
        from d2.mpq import MPQSet
        self._workers = {}
        if not isinstance(self.src, MPQSet) or not getattr(self.src, "cache_dir", None):
            return
        try:
            import multiprocessing
            from d2 import soundworker
            ctx = multiprocessing.get_context("spawn")
            self._outq = ctx.Queue()
            hi_sweep, lo_sweep = self._sweep_lists()
            for key, sweep in (("hi", hi_sweep), ("lo", lo_sweep)):
                inq = ctx.Queue()
                proc = ctx.Process(target=soundworker.worker_main,
                                   args=(assets.d2_path, self.src.cache_dir, self.music_dir, inq, self._outq, sweep),
                                   daemon=True)
                proc.start()
                self._workers[key] = (proc, inq)
        except Exception as e:
            print("  sound worker:", e)
            self._workers = {}

    @property
    def _worker(self):
        return self._workers.get("lo", (None,))[0] if getattr(self, "_workers", None) else None

    def _music_file(self, path):
        from d2.soundworker import music_file
        return music_file(self.music_dir, path)

    def _quick(self, path):
        """Can this file be read without unpacking (cached, or an extracted folder)?"""
        if path.startswith(MUSIC_DIR):
            return os.path.exists(self._music_file(path))
        cached = getattr(self.src, "cached", None)
        return cached(path) if cached is not None else True

    def request(self, path, hi=False):
        if not hasattr(self, "loaded"):
            return
        if path in self.loaded or path in self.pending:
            return
        if self._quick(path):
            if path.startswith(MUSIC_DIR):
                self.loaded[path] = True
            else:
                self._load_now(path)
            return
        key = "hi" if (hi or path.startswith(MUSIC_DIR) or path.startswith(SFX_DIRS[1])) else "lo"
        w = getattr(self, "_workers", {}).get(key)
        if w is not None and w[0].is_alive():
            self.pending.add(path)
            w[1].put(path)
        elif not path.startswith(MUSIC_DIR) or not self._workers:
            self._load_now(path)

    def _load_now(self, path):
        try:
            data = self.src.read(path)
        except Exception:
            self.loaded[path] = None
            return
        if path.startswith(MUSIC_DIR):
            try:
                with open(self._music_file(path), "wb") as f:
                    f.write(data)
                self.loaded[path] = True
            except Exception:
                self.loaded[path] = None
            return
        try:
            self.loaded[path] = pygame.mixer.Sound(file=io.BytesIO(data))
        except Exception:
            self.loaded[path] = None

    def update(self):
        """Every frame: take what the unpackers have done; start wanted voices / music / late sounds."""
        if not self.ok:
            return
        if getattr(self, "_workers", None):
            n = 0
            while n < 8:
                try:
                    path, good = self._outq.get_nowait()
                except Exception:
                    break
                n += 1
                self.pending.discard(path)
                if not good:
                    self.loaded[path] = None
                elif path.startswith(MUSIC_DIR):
                    self.loaded[path] = True
                else:
                    self._load_now(path)          # (now a quick read from the MPQ cache)
        if self.late:
            now = time.time()
            keep = []
            for path, name, vol, t0 in self.late:
                snd = self.loaded.get(path)
                if snd and snd is not True:
                    if now - t0 < 0.9:
                        self._start(snd, name, vol)
                elif path in self.pending and now - t0 < 0.9:
                    keep.append((path, name, vol, t0))
            self.late = keep
        if self.voice_want:
            path, t0 = self.voice_want
            if time.time() - t0 > 60:
                self.voice_want = None
            elif self.loaded.get(path):
                self.voice_want = None
                self._play_voice(self.loaded[path], path)
        if self.music_want and self.music_want != self.music_now:
            self._try_music(self.music_want)

    def warm(self, names):
        """Unpack these sounds now, before they are needed (an area's monsters, the party's skills)."""
        if not self.ok:
            return
        for n in names:
            if n and n not in self._warmed:
                self._warmed.add(n)
                for path in self._variants(n):
                    self.request(path)

    # ------------------------------------------------------------ playing
    def _vol(self):
        return max(0, min(100, int(self.opts.get("sound_volume", 80)))) / 100.0

    def play(self, name, unit=None, world=None, vol=1.0, min_gap=0.06):
        """Play one of the sound's variants (quietly or not at all when the unit is far off)."""
        if not self.ok or not name:
            return
        now = time.time()
        if now - self.last.get(name, 0) < min_gap:
            return
        paths = self._variants(name)
        if not paths:
            return
        path = random.choice(paths)
        v = vol * self._vol() * _int(self._row(name).get("volume"), 255) / 255.0
        if unit is not None and world is not None and getattr(world, "player", None) is not None:
            try:
                d = world.udist(unit, world.player)
            except Exception:
                d = 0
            if d > 34:
                return
            v *= max(0.25, 1.0 - d / 40.0)
        if v <= 0.01:
            return
        self.last[name] = now
        snd = self.loaded.get(path)
        if snd is None or snd is True:
            if path not in self.loaded:
                self.request(path)
            if path in self.pending or (self.loaded.get(path) and self.loaded[path] is not True):
                self.late.append((path, name, v, now))
                if self.loaded.get(path):
                    self.update()
            return
        self._start(snd, name, v)

    def _start(self, snd, name, v):
        try:
            ch = snd.play()
            if ch is not None:
                ch.set_volume(v)
        except Exception:
            pass

    # NPC speech
    def speak(self, name):
        """An NPC's voiced line (one at a time: a new one stops the last)."""
        if not self.ok:
            return False
        self.stop_voice()
        paths = self._variants(name)
        if not paths:
            return False
        path = paths[0]
        snd = self.loaded.get(path)
        if snd:
            self._play_voice(snd, path)
        else:
            self.request(path)
            self.voice_want = (path, time.time())
        return True

    def _play_voice(self, snd, path):
        try:
            ch = pygame.mixer.Channel(0)
            ch.set_volume(self._vol())
            ch.play(snd)
            self.voice_path = path
        except Exception:
            pass

    def stop_voice(self):
        self.voice_want = None
        if self.ok:
            try:
                pygame.mixer.Channel(0).stop()
            except Exception:
                pass

    # music and ambience
    def _music_vol(self):
        return max(0, min(100, int(self.opts.get("music_volume", 70)))) / 100.0

    def set_music(self, name):
        if not self.ok or name == self.music_want or name in self.failed:
            return
        self.music_want = name
        if not name:
            try:
                pygame.mixer.music.fadeout(800)
            except Exception:
                pass
            self.music_now = None
            return
        self._try_music(name)

    def _try_music(self, name):
        paths = self._variants(name)
        if not paths:
            self.music_want = None
            return
        path = paths[0]
        if not self.loaded.get(path):
            if path not in self.loaded:
                self.request(path)
            elif self.loaded.get(path) is None and path not in self.pending:
                self.failed.add(name)            # (not in this install: stay quiet, don't retry)
                self.music_want = None
            return
        try:
            pygame.mixer.music.fadeout(600)
            pygame.mixer.music.load(self._music_file(path))
            pygame.mixer.music.set_volume(self._music_vol() * _int(self._row(name).get("volume"), 110) / 160.0)
            pygame.mixer.music.play(-1 if _int(self._row(name).get("loop"), 1) else 0, fade_ms=1500)
            self.music_now = name
        except Exception as e:
            print("  music:", e)
            self.music_want = None

    def set_ambient(self, name):
        if not self.ok or name == self.ambient_now or name in self.failed:
            return
        self.ambient_now = name
        ch = pygame.mixer.Channel(1)
        try:
            ch.fadeout(800)
        except Exception:
            pass
        if not name:
            return
        paths = self._variants(name)
        if not paths:
            return
        snd = self.loaded.get(paths[0])
        if not snd or snd is True:
            if paths[0] in self.loaded and not snd and paths[0] not in self.pending:
                self.failed.add(name)
                return
            self.request(paths[0])
            self.ambient_now = None             # (try again once it is unpacked)
            return
        try:
            ch.set_volume(0.45 * self._vol())
            ch.play(snd, loops=-1, fade_ms=1200)
        except Exception:
            pass

    def area(self, level_id):
        """The area's song and ambience (D2's Levels.txt SoundEnv)."""
        env = self.level_env.get(level_id)
        if env is None:
            return
        self.set_music(self.env_song.get(env))
        self.set_ambient(self.env_amb.get(env))

    def apply_volumes(self):
        if not self.ok:
            return
        try:
            if self.music_now:
                pygame.mixer.music.set_volume(self._music_vol() * _int(self._row(self.music_now).get("volume"), 110) / 160.0)
            pygame.mixer.Channel(1).set_volume(0.45 * self._vol())
            pygame.mixer.Channel(0).set_volume(self._vol())
        except Exception:
            pass

    # ------------------------------------------------------------ game events
    def _weapon_class(self, unit):
        eq = getattr(unit, "equipment", None) or {}
        w = eq.get("weapon")
        if w is None:
            return "hth"
        wc = (getattr(w, "wclass", "") or "").lower()
        return wc or "1hs"

    def _mon_row(self, m):
        sid = self.mon_snd_id.get((getattr(m, "d2id", None) or getattr(m, "kind", "") or "").lower())
        return self.monsound.get(sid) if sid else None

    def _hero(self, unit):
        return getattr(unit, "is_player", False) or (getattr(unit, "cls", None) in CLASS_SND and
                                                       getattr(unit, "skills", None) is not None)

    def event(self, world, ev):
        """A game event is being shown: its sound."""
        if not self.ok:
            return
        kind = ev[0]
        try:
            if kind == "attack":
                unit, skill = ev[1], ev[3]
                self._last_attacker = unit
                if self._hero(unit):
                    if skill == "kick":
                        self.play("weapon_kick", unit, world)
                    elif skill not in ("cast", "resurrect"):
                        self.play(SWING.get(self._weapon_class(unit), "weapon_1hs_small"), unit, world)
                elif getattr(unit, "ai", "") != "npc":
                    r = self._mon_row(unit)
                    if r:
                        self.play(r.get("attack1") or "", unit, world)
                        self.play(r.get("weapon1") or "", unit, world)
            elif kind == "projectile":
                unit, missile = ev[1], (ev[5] if len(ev) > 5 else None)
                self._last_attacker = unit
                ts = self.missile_snd.get((missile or "").lower(), ("", ""))[0]
                if ts:
                    self.play(ts, unit, world)
                elif ev[4] == "arrow" and self._hero(unit):
                    self.play("weapon_xbow" if self._weapon_class(unit) == "xbw" else "weapon_bow", unit, world)
            elif kind in ("nova", "explosion"):
                missile = ev[5] if kind == "nova" and len(ev) > 5 else (ev[2] if kind == "explosion" and len(ev) > 2 else None)
                t, h = self.missile_snd.get((missile or "").lower(), ("", ""))
                self.play(h or t, ev[1] if kind == "nova" else None, world)
            elif kind == "flames":
                t, h = self.missile_snd.get((ev[2] or "").lower(), ("", ""))
                self.play(t or h, None, world)
            elif kind == "damage":
                unit, amount = ev[1], ev[2]
                att = getattr(self, "_last_attacker", None)
                if att is not None and self._hero(att):
                    self.play(IMPACT.get(self._weapon_class(att), "impact_blunt"), unit, world, vol=0.8)
                elif att is not None:
                    self.play("impact_punch", unit, world, vol=0.6)
                if self._hero(unit):
                    if amount * 12 >= max(1, unit.max_hp):
                        self.play("%s_hit" % CLASS_SND.get(getattr(unit, "cls", ""), "barbarian"), unit, world,
                                  min_gap=0.35)
                else:
                    r = self._mon_row(unit)
                    if r:
                        self.play(r.get("hitsound") or "", unit, world, min_gap=0.15)
            elif kind == "death":
                unit = ev[1]
                if self._hero(unit):
                    self.play("%s_death" % CLASS_SND.get(getattr(unit, "cls", ""), "barbarian"), unit, world)
                else:
                    r = self._mon_row(unit)
                    if r:
                        self.play(r.get("deathsound") or "", unit, world)
            elif kind == "levelup":
                self.play("cursor_level_up")
            elif kind == "pickup":
                it = ev[2]
                if getattr(it, "kind", "") == "gold":
                    self.play("item_gold")
                else:
                    self.play(self.item_snd.get(getattr(it, "code", ""), ("", ""))[1] or "item_flippy")
            elif kind == "drop":
                it = ev[2]
                if getattr(it, "kind", "") == "gold":
                    self.play("item_gold", vol=0.7)
                else:
                    self.play(self.item_snd.get(getattr(it, "code", ""), ("", ""))[0] or "item_flippy", vol=0.8)
            elif kind == "object":
                self.play(self._object_sound(ev[1]))
            elif kind == "sound":
                self.play(ev[1], ev[2] if len(ev) > 2 else None, world)
            elif kind == "skill_sound":
                for nm in self.skill_names(ev[1]):
                    self.play(nm, ev[2] if len(ev) > 2 else None, world)
            elif kind == "log":
                if str(ev[1]).startswith("Quest completed"):
                    self.play("cursor_questdone")
        except Exception:
            pass

    def skill_names(self, skill):
        """A skill's D2 sounds: the cast (stsound), the target's (tgtsound: Corpse Explosion's blast)
        and the state it puts on (a curse's own sound: Amplify Damage, Iron Maiden...)."""
        r = self.skill_row.get(skill) or {}
        out = []
        for k in ("stsound", "stsoundclass"):
            if r.get(k):
                out.append(r[k])
                break
        if not out and r.get("dosound"):
            out.append(r["dosound"])
        if r.get("tgtsound"):
            out.append(r["tgtsound"])
        st = r.get("auratargetstate") or ""
        if st and self.state_snd.get(st) and (r.get("auratargetstate") != r.get("aurastate")):
            out.append(self.state_snd[st])
        elif r.get("aurastate") and self.state_snd.get(r["aurastate"]) and r.get("aura") != "1":
            out.append(self.state_snd[r["aurastate"]])
        for mk in ("srvmissile", "cltmissile", "srvmissilea", "cltmissilea"):
            m = (r.get(mk) or "").lower()
            if m and m in self.missile_snd:
                if self.missile_snd[m][0]:
                    out.append(self.missile_snd[m][0])     # (its hit sound plays where it lands)
                break
        return out

    def warm_world(self, world):
        """Unpack what this area will need first: its monsters' sounds and the party's skills."""
        names = []
        try:
            for m in list(getattr(world, "monsters", []))[:400]:
                r = self._mon_row(m)
                if r:
                    names += [r.get("attack1"), r.get("weapon1"), r.get("hitsound"), r.get("deathsound")]
            heroes = list(getattr(world, "party", None) or [world.player])
            for h in heroes:
                cs = CLASS_SND.get(getattr(h, "cls", ""), "")
                names += [cs + "_hit", cs + "_death"]
                for sk, lv in getattr(getattr(h, "skills", None), "levels", {}).items():
                    if lv:
                        names += self.skill_names(sk)
        except Exception:
            pass
        # (the skill's own cast sound is played by name; a missile's sounds are names too)
        self.warm([n for n in names if n])

    @staticmethod
    def _object_sound(o):
        k = (o.get("kind") or "").lower()
        n = (o.get("name") or "").lower()
        if "waypoint" in k or "waypoint" in n:
            return "object_waypoint_open"
        if "xbarrel" in k or "exploding" in n:
            return "object_barrel_explode"
        if "barrel" in k or "barrel" in n or "crate" in n or "box" in n:
            return "object_wood_break"
        if any(w in k or w in n for w in ("urn", "jar", "pot", "vase")):
            return "object_urn_break"
        if "basket" in n:
            return "object_basket"
        if "door" in k or "door" in n:
            return "object_door_gate_open" if "gate" in n else "object_door_wood_open"
        if "gate" in k or "gate" in n:
            return "object_door_gate_open"
        if "shrine" in k or "shrine" in n:
            return "object_shrine_holy"
        if "casket" in n or "coffin" in n or "sarcophag" in n:
            return "object_casket"
        if "corpse" in n or "bones" in n or "body" in n:
            return "object_corpse_loot"
        if "rock" in n:
            return "object_rockpile"
        if "chest" in k or "chest" in n:
            return "object_chest_large" if ("large" in n or "big" in n) else "object_chest_small"
        return "object_chest_small" if k in ("chest", "container") else ""

    def quit(self):
        for proc, inq in getattr(self, "_workers", {}).values():
            try:
                inq.put(None)
            except Exception:
                pass
