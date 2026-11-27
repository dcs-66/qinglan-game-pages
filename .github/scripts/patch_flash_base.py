from pathlib import Path
import re
import sys

site = Path(sys.argv[1] if len(sys.argv) > 1 else 'site')
p = site / 'js' / 'combat' / 'enemy.js'
if not p.exists():
    raise SystemExit(f'missing {p}')
s = p.read_text(encoding='utf-8').replace('\r\n', '\n')

old_call = 'if (!fromPet) flashEnemyMesh(this.mesh);'
s, n_call = re.subn(r'(?m)^(\s*)flashEnemyMesh\(this\.mesh\);',
                    r'\1if (!fromPet) flashEnemyMesh(this.mesh);', s, count=1)
if s.count(old_call) != 1:
    raise SystemExit(f'fromPet flash call count={s.count(old_call)}')

old_start = "    this.mesh.traverse(c => { if (c.isMesh && c.material && c.material.emissive) { c._origEmissive = c.material.emissive.getHex(); c.material.emissive.setHex(glow); c.material.emissiveIntensity = 0.85; } });"
new_start = """    this.mesh.traverse(c => {
      if (c.isMesh && c.material && c.material.emissive) {
        // 预警只还原真正的底色，不能把闪白时的白色记成原色。
        if (c._baseEmissive === undefined) {
          c._baseEmissive = c._origEmissive !== undefined ? c._origEmissive : c.material.emissive.getHex();
        }
        if (c._baseEmissiveInt === undefined) c._baseEmissiveInt = c.material.emissiveIntensity;
        c._origEmissive = c._baseEmissive;
        c.material.emissive.setHex(glow);
        c.material.emissiveIntensity = 0.85;
      }
    });"""
if s.count(old_start) != 1:
    raise SystemExit(f'start telegraph anchor count={s.count(old_start)}')
s = s.replace(old_start, new_start, 1)

new_func = """function flashEnemyMesh(mesh) {
  if (!mesh) return;
  // 每只模型只记录一次真正的材质底色：攻击预警的红光、闪白中的白色都不能当原色。
  // 同一轮闪白内重复命中只重置 130ms 计时器，结束时恢复到首次记录的原色。
  let st = mesh.userData.__flashState;
  if (!st || !st.timer) {
    const nodes = [];
    mesh.traverse(o => {
      if (!o.material || !o.material.emissive) return;
      if (nodes.some(n => n.material === o.material)) return;
      nodes.push(o);
    });
    const bases = nodes.map(o => {
      const base = o._baseEmissive !== undefined ? o._baseEmissive
        : (o._origEmissive !== undefined ? o._origEmissive : o.material.emissive.getHex());
      if (o._baseEmissive === undefined) o._baseEmissive = base;
      if (o._baseEmissiveInt === undefined) o._baseEmissiveInt = o.material.emissiveIntensity;
      return base;
    });
    st = {
      mats: nodes.map(o => o.material),
      origs: bases,
      origInt: nodes.map(o => o._baseEmissiveInt !== undefined ? o._baseEmissiveInt : o.material.emissiveIntensity),
      timer: null
    };
    mesh.userData.__flashState = st;
  }
  if (st.timer) clearTimeout(st.timer);
  st.mats.forEach(m => { if (m.emissive) { m.emissive.setHex(0xffffff); m.emissiveIntensity = 1.1; } });
  st.timer = setTimeout(() => {
    st.mats.forEach((m, i) => {
      if (m.emissive && st.origs[i] !== null) {
        m.emissive.setHex(st.origs[i]);
        m.emissiveIntensity = st.origInt[i];
      }
    });
    st.timer = null;
  }, 130);
}
"""
pat = re.compile(r'function flashEnemyMesh\(mesh\) \{\n.*?\n\}\n', re.S)
m = pat.search(s)
if not m:
    raise SystemExit('flash function not found')
s = s[:m.start()] + new_func + s[m.end():]

if s.count('_baseEmissive') < 10:
    raise SystemExit(f'base refs {s.count("_baseEmissive")}')
if s.count('if (!fromPet) flashEnemyMesh(this.mesh);') != 1:
    raise SystemExit('fromPet flash call lost')
if 'const origs = mats.map' in s:
    raise SystemExit('old flash function still present')

p.write_text(s, encoding='utf-8', newline='\n')

# 同步版本串：旧 Cloudflare 构建仍是 20261125proc2，apply_boss 脚本会先写成 bossrestore。
BUILD = '20261127bossflash'
ip = site / 'index.html'
if ip.exists():
    h = ip.read_text(encoding='utf-8')
    h = h.replace('20261125proc2', BUILD).replace('20261127bossrestore', BUILD)
    h = re.sub(r'(id="start-version"[^>]*>)[^<]*(</div>)',
               r'\g<1>BUILD 20261127bossflash · 闪白修复\g<2>', h, count=1)
    game_build = '''window.GAME_BUILD = {
    id: '20261127bossflash',
    time: '2026-11-27 15:13',
    label: '闪白修复',
    note: 'Boss 模型归位保留 · 宠物攻击不再触发闪白，连击也能恢复原色'
  };'''
    h = re.sub(r'window\.GAME_BUILD\s*=\s*\{[\s\S]*?\};', game_build, h, count=1)
    ip.write_text(h, encoding='utf-8', newline='\n')
    print(f'index version -> {BUILD}')

print(f'patched {p}: baseRefs={s.count("_baseEmissive")} flash={s.count("function flashEnemyMesh")}')
