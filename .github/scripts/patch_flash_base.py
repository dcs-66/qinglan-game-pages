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

# 机甲战士（断塔·蚀冠）最终修复：
# mech_warrior.glb 的 Mech_Take 长镜是“拆甲/变形”素材，直接当 idle/登场会随机把机身拆散，
# 实战里只剩镰刀和披风（用户看到“突然出现、只看见一部分”）。这里改用 Blender 绑定姿势
# 烘焙出的静态全身 GLB，彻底绕开长镜；水平居中、按目标高度落地，不再靠猜旋转/偏移。
# 注意：源文件里 demon_king 出现两次（基础 ENEMY_DEFS + 末尾 Object.assign 覆盖），
# 两处都必须替换，否则末尾覆盖会把静态模型再改回会拆甲的 mech_warrior.glb。
gp = site / 'js' / 'data' / 'game-data.js'
if gp.exists():
    g = gp.read_text(encoding='utf-8')
    new_block = """  demon_king: {
    name: '断塔·蚀冠', hp: 350, attack: 28, gold: 300, exp: 200, color: 0xee0000,
    isBoss: true, speed: 1.5, atkRange: 2.5, atkCD: 1400, weakY: 3.5, aiType: 'summoner',
    // 绑定姿势静态全身模型：避开 Mech_Take 拆甲长镜，祭坛上不会再只剩镰刀/披风
    model: 'https://aka.doubaocdn.com/s/DimwHxsZKC', modelH: 4.4, skipPreload: true,
  },"""
    g, n_block = re.subn(r"  demon_king: \{[\s\S]*?\n  \},", new_block, g, count=2)
    if n_block != 2:
        raise SystemExit(f'demon_king block replace count={n_block}')
    gp.write_text(g, encoding='utf-8', newline='\n')
    print(f'patched demon_king static body: {n_block} block(s)')

# 祭坛机甲常被深色材质吃掉轮廓：给断塔·蚀冠挂一盏冷色近身补光，只影响这一只 Boss。
ep = site / 'js' / 'combat' / 'enemy.js'
if ep.exists():
    e = ep.read_text(encoding='utf-8')
    old_mesh = "    this.mesh = createEnemyMesh(id);\n    this.mesh.position.set(pos.x, 0, pos.z);\n"
    if old_mesh not in e:
        raise SystemExit('enemy mesh init anchor missing')
    light_code = """    this.mesh = createEnemyMesh(id);
    this.mesh.position.set(pos.x, 0, pos.z);
    if (id === 'demon_king') {
      // 静态银甲在祭坛暗红光下会糊成一团黑；近身冷光把肩甲/头盔/腿甲从背景里拉出来。
      const bossLight = new THREE.PointLight(0x9fc8ff, 2.8, 14, 2);
      bossLight.position.set(0, 3.2, 0);
      bossLight.castShadow = false;
      this.mesh.add(bossLight);
    }
"""
    e = e.replace(old_mesh, light_code, 1)
    ep.write_text(e, encoding='utf-8', newline='\n')
    print('patched demon_king boss light')

# 同步版本串：旧 Cloudflare 构建仍是 20261125proc2，apply_boss 脚本会先写成 bossrestore。
BUILD = '20261127mechstand'
ip = site / 'index.html'
if ip.exists():
    h = ip.read_text(encoding='utf-8')
    h = h.replace('20261125proc2', BUILD).replace('20261127bossrestore', BUILD).replace('20261127bossflash', BUILD).replace('20261127mechfix', BUILD)
    h = re.sub(r'(id="start-version"[^>]*>)[^<]*(</div>)',
               r'\g<1>BUILD 20261127mechstand · 机甲站立\g<2>', h, count=1)
    game_build = '''window.GAME_BUILD = {
    id: '20261127mechstand',
    time: '2026-11-27 19:35',
    label: '机甲站立',
    note: 'Boss 模型改用绑定姿势静态全身 · 避开拆甲长镜 · 近身冷光补轮廓'
  };'''
    h = re.sub(r'window\.GAME_BUILD\s*=\s*\{[\s\S]*?\};', game_build, h, count=1)
    ip.write_text(h, encoding='utf-8', newline='\n')
    print(f'index version -> {BUILD}')

print(f'patched {p}: baseRefs={s.count("_baseEmissive")} flash={s.count("function flashEnemyMesh")}')
