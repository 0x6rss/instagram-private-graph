                                                        

const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

                                                                     
                                                                                   
const UI_ICON_NAMES = new Set([
  'settings','refresh','zap','alert-triangle','close','info','check',
  'shield-check','shield-alert','signal-high','signal-medium','signal-low','signal-none',
  'user','users','file-text','network','target','activity','zoom-in','zoom-out','maximize',
  'chevron-right','external-link','arrow-left-right','arrow-left','arrow-right','arrow-down-right',
  'heart','message-circle','tag','bell','clock','star','search','globe','map-pin','list',
  'sparkles','code','image','calendar','lock','eye','grid','mail','cake','circle','percent','volume-x',
]);
const UI_ICON_ALIASES = Object.freeze({
  '◎':'target', '✦':'sparkles', '↗':'external-link', '→':'arrow-right', '↘':'arrow-down-right',
  '◇':'search', '⌕':'search', '↔':'arrow-left-right', '←':'arrow-left', '♥':'heart',
  '◌':'message-circle', '#':'tag', '◉':'image', '•':'info', '·':'circle', '○':'circle',
  '⌘':'users', '◷':'clock', '★':'star', '☆':'star', '–':'volume-x', '!':'alert-triangle',
  '✓':'check', '◐':'signal-medium', '◒':'lock', '♙':'users', '▦':'image', '@':'globe',
  '⌖':'map-pin', '≡':'list', 'f':'globe', '{}':'code', '✉':'mail', '%':'percent',
  '×':'close', '↻':'refresh', '▤':'file-text', '✣':'activity', '▥':'signal-medium',
});
function uiIcon(name, className='') {
  const raw = String(name || 'info');
  const candidate = UI_ICON_ALIASES[raw] || raw.toLowerCase();
  const icon = UI_ICON_NAMES.has(candidate) ? candidate : 'info';
  const safeClass = String(className || '').replace(/[^a-z0-9 _-]/gi, '').trim();
  return `<svg class="ui-icon${safeClass ? ` ${safeClass}` : ''}" aria-hidden="true" focusable="false"><use href="#ui-${icon}"></use></svg>`;
}

                                                                                  
                                                                             
const appI18n = window.AppI18n || null;
function i18nT(key, vars={}, fallback='') {
  if (appI18n && typeof appI18n.t === 'function') {
    const value = appI18n.t(key, vars);
    if (value && value !== key) return value;
  }
  return fallback || String(key || '');
}
function i18nText(value) {
  return appI18n && typeof appI18n.translateText === 'function'
    ? appI18n.translateText(value)
    : String(value ?? '');
}
function translateUi(root=document) {
  if (appI18n && typeof appI18n.translate === 'function') appI18n.translate(root);
}
function formatUiNumber(value, options={}) {
  if (appI18n && typeof appI18n.formatNumber === 'function') {
    return appI18n.formatNumber(value, options);
  }
  const number = Number(value);
  return Number.isFinite(number) ? new Intl.NumberFormat('en-US', options).format(number) : String(value ?? '');
}
function formatUiPercent(value, options={}) {
  if (appI18n && typeof appI18n.formatPercent === 'function') {
    return appI18n.formatPercent(value, options);
  }
  const number = Number(value);
  return Number.isFinite(number) ? `${number}%` : String(value ?? '');
}
function compareUiText(a, b) {
  if (appI18n && typeof appI18n.compareText === 'function') return appI18n.compareText(a, b);
  return String(a ?? '').localeCompare(String(b ?? ''), 'en', {sensitivity:'base'});
}

                              
const state = {
  username: null,
  data: null,                       
  text: null,                       
  filtered: [],                                       
  sortKey: 'score',
  sortDir: 'desc',
  search: '',
  minScore: 0,
  tiers: {
    verified:1, high_probability:1,
    medium_probability:0, low_probability:0, noise:0,
             
    intimate:1, known:1, acquaintance:1, algorithmic:0,
  },
  flags: { priv:0, ver:0 },
  selectedPk: null,
  graphController: null,
  loadRequestId: 0,
  loadAbortController: null,
  pendingUsername: null,
  users: [],
};

const HOP_CLASS_FLAG = {
  'verified':           {icon:'shield-check', cls:'STABLE', titleKey:'flag.veryHigh'},
  'high_probability':   {icon:'signal-high', cls:'HOP1',   titleKey:'flag.high'},
  'medium_probability': {icon:'signal-medium', cls:'HOPL', titleKey:'flag.medium'},
  'low_probability':    {icon:'signal-low', cls:'HOP2',    titleKey:'flag.low'},
  'noise':              {icon:'signal-none', cls:'HOP2',   titleKey:'flag.insufficient'},
  'unknown':            {icon:'info', cls:'HOPU',          titleKey:'flag.unknown'},
                                                                                      
  '1hop_stable':    {icon:'shield-check',  cls:'STABLE', titleKey:'flag.veryHigh'},
  '1hop_strong':    {icon:'signal-high',   cls:'HOP1',   titleKey:'flag.high'},
  '1hop_confirmed': {icon:'signal-medium', cls:'HOPL',   titleKey:'flag.medium'},
  '1hop_likely':    {icon:'signal-low',    cls:'HOPL',   titleKey:'flag.low'},
  '2hop_suspect':   {icon:'signal-none',   cls:'HOP2',   titleKey:'flag.insufficient'},
};

                            
async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    const txt = await r.text().catch(()=>'');
    throw new Error(`${path} -> ${r.status} ${txt.slice(0,200)}`);
  }
  return r.json();
}
async function apiText(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.text();
}

                               
let currentStatusMessage = null;
function setStatus(msg, kind='', localization=null) {
  const el = $('#status');
  if (!el) return;
  currentStatusMessage = localization ? {...localization, kind} : {raw:String(msg || ''), kind};
  el.textContent = i18nText(msg || '');
  el.className = 'status ' + (kind||'');
}
function setStatusKey(key, vars={}, kind='', fallback='') {
  setStatus(i18nT(key, vars, fallback), kind, {key, vars:{...vars}, fallback});
}
function refreshLocalizedStatus() {
  if (!currentStatusMessage) return;
  if (currentStatusMessage.key) {
    const {key, vars, kind, fallback} = currentStatusMessage;
    setStatusKey(key, vars, kind, fallback);
  } else {
    setStatus(currentStatusMessage.raw, currentStatusMessage.kind);
  }
}

                                  
function renderUserOptions(users=state.users, preferredUsername='') {
  const sel = $('#userSelect');
  if (!sel) return;
  const selected = preferredUsername || sel.value || state.pendingUsername || state.username || '';
  sel.innerHTML = '';
  users.forEach(user => {
    const opt = document.createElement('option');
    opt.value = user.username;
    opt.dataset.ready = user.has_engine_output ? '1' : '0';
    const readiness = user.has_engine_output
      ? i18nT('common.ready', {}, 'Ready')
      : i18nT('common.dataMissing', {}, 'Data incomplete');
    opt.textContent = `${user.username} — ${readiness}`;
    sel.appendChild(opt);
  });
  if (selected && [...sel.options].some(option => option.value === selected)) sel.value = selected;
  translateUi(sel);
}

async function loadUsers({autoLoad=true, preferredUsername=null}={}) {
  setStatusKey('status.accountsLoading', {}, 'busy', 'Loading saved accounts…');
  const users = await api('/api/users');
  state.users = Array.isArray(users) ? users.slice() : [];
  const sel = $('#userSelect');
  renderUserOptions(state.users, preferredUsername || state.pendingUsername || state.username);
  setStatusKey('status.accountsFound', {count:users.length}, 'ok', `${users.length} accounts found`);
  if (users.length) {
    const requested = preferredUsername || state.pendingUsername || state.username;
    const first = users.find(u => u.username === requested)
      || users.find(u => u.has_engine_output) || users[0];
    sel.value = first.username;
    if (autoLoad) await loadUser(first.username);
  }
  return users;
}

async function loadUser(username) {
  const requestedUsername = String(username || '').trim();
  if (!requestedUsername) return false;
  const requestId = ++state.loadRequestId;
  state.pendingUsername = requestedUsername;
  ++avatarWarmGeneration;
  if (state.loadAbortController) state.loadAbortController.abort();
  const controller = new AbortController();
  state.loadAbortController = controller;
  setStatusKey('status.userLoading', {username:requestedUsername}, 'busy', `Loading ${requestedUsername}…`);
  let data;
  let report = '';
  try {
    [data, report] = await Promise.all([
      api(`/api/users/${encodeURIComponent(requestedUsername)}/data`, {signal:controller.signal}),
      apiText(`/api/users/${encodeURIComponent(requestedUsername)}/report`, {signal:controller.signal})
        .catch(error => {
          if (error && error.name === 'AbortError') throw error;
          return '';
        }),
    ]);
  } catch (e) {
    controller.abort();
    if (requestId !== state.loadRequestId || (e && e.name === 'AbortError')) return false;
    state.loadAbortController = null;
    setStatusKey('status.userNotFound', {username:requestedUsername}, 'err', `No result found for ${requestedUsername}`);
    state.data = null;
    $('#main').classList.add('hidden');
    return false;
  }
  if (requestId !== state.loadRequestId || state.pendingUsername !== requestedUsername) return false;
  const responseUsername = data && data.username ? String(data.username).replace(/^@/, '').toLowerCase() : '';
  if (responseUsername && responseUsername !== requestedUsername.replace(/^@/, '').toLowerCase()) {
    state.loadAbortController = null;
    state.data = null;
    $('#main').classList.add('hidden');
    setStatusKey('status.staleBlocked', {}, 'err', 'A stale response for another account was blocked; try again.');
    return false;
  }
  state.loadAbortController = null;
  state.username = requestedUsername;
  state.data = data;
  state.text = report;
  state.selectedPk = null;
  state.graphController = null;
  const select = $('#userSelect');
  if (select && [...select.options].some(option => option.value === requestedUsername)) {
    select.value = requestedUsername;
  }
  $('#main').classList.remove('hidden');
  if (document.activeElement !== $('#newQuery')) $('#newQuery').value = requestedUsername;
  render();
  warmAvatarCache(data, requestedUsername);
  setStatusKey('status.userLoaded', {
    username:requestedUsername,
    count:(data.people || []).length,
  }, 'ok', `Loaded ${requestedUsername} — ${(data.people || []).length} people`);
  return true;
}

async function runEngine() {
  if (!state.username) return;
  const targetUsername = state.username;
  const drop = $('#dropAlgo').checked ? '1' : '0';
  setStatusKey('status.scoresRefreshing', {username:targetUsername}, 'busy', `Recalculating scores for ${targetUsername}…`);
  $('#runBtn').disabled = true;
  try {
    const r = await api(`/api/users/${encodeURIComponent(targetUsername)}/run?drop_algorithmic=${drop}`,
                         {method:'POST'});
    setStatusKey('status.scoresUpdated', {}, 'ok', 'Scores updated');
    if (state.pendingUsername === targetUsername) await loadUser(targetUsername);
  } catch (e) {
    setStatusKey('status.scoresFailed', {}, 'err', 'Scores could not be updated');
  } finally {
    $('#runBtn').disabled = false;
  }
}

                               
function render() {
  const d = state.data; if (!d) return;
  $('#statTarget').textContent = d.username;
  $('#statTargetPk').textContent = `pk=${d.target_pk||'?'}`;
  const tc = dashboardTierCounts();
                            
  $('#statIntimate').textContent = tc.verified;
  $('#statKnown').textContent    = tc.high_probability;
  $('#statAcq').textContent      = tc.medium_probability;
  $('#statAlgo').textContent     = tc.low_probability;
  $('#statNoise').textContent    = tc.noise;
  $('#statTotal').textContent    = d.people.length;

  const scoredCount = d.people.filter(hasValidModelScore).length;
  $('#statBidir').textContent = i18nT('stats.scoreCoverage', {
    scored:scoredCount, unscored:d.people.length - scoredCount,
  }, `${scoredCount} scored · ${d.people.length - scoredCount} unscored`);

  renderDashboardChrome();
  applyFilters();
  renderTargetIntelHuman();
  renderBootstrap();
  if ($('#tab-graph').classList.contains('active')) drawGraph();
  else if ($('#tab-report').classList.contains('active')) renderReport();
  else $('#graphContainer').innerHTML = '';
  translateUi($('#main'));
}

                                
function applyFilters() {
  const d = state.data;
  const q = state.search.toLowerCase();
  state.filtered = d.people.filter(p => {
    const tier = canonicalTier(p);
                                                                                    
    const selectedTier = tier === 'unknown' ? 'noise' : tier;
    if (!state.tiers[selectedTier]) return false;
    const score = modelScore(p);
    if (score == null ? state.minScore > 0 : score < state.minScore) return false;
    if (state.flags.priv && !p.is_private) return false;
    if (state.flags.ver && !p.is_verified) return false;
    if (q) {
      const hay = `${p.username||''} ${p.full_name||''} ${p.pk}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
         
  state.filtered.sort(cmp);
  $('#visibleCount').textContent = i18nT('people.visibleCount', {
    visible:state.filtered.length, total:d.people.length,
  }, `${state.filtered.length} / ${d.people.length} people`);
  renderTable();
}

function cmp(a, b) {
  const k = state.sortKey;
  if (k === 'score') {
    const av = modelScore(a);
    const bv = modelScore(b);
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    return state.sortDir === 'desc' ? bv - av : av - bv;
  }
  let av = a[k], bv = b[k];
  if (av == null) av = '';
  if (bv == null) bv = '';
  if (typeof av === 'number') {
    return state.sortDir === 'desc' ? bv - av : av - bv;
  }
  av = String(av).toLowerCase(); bv = String(bv).toLowerCase();
  return state.sortDir === 'desc'
    ? compareUiText(bv, av) : compareUiText(av, bv);
}

function renderTable() {
  const tb = $('#peopleBody');
  const rows = [];
  for (const p of state.filtered) {
    const flags = personFlags(p);
    const ev = personEvidenceChips(p);
    const tier = canonicalTier(p);
    const score = modelScore(p);
    const scoreDisplay = formatModelScore(p);
    const scoreTitle = modelScoreDescription(p);
    const tierLabel = localizedTierLabel(p);
    rows.push(`
      <tr data-pk="${p.pk}" class="${String(p.pk) === state.selectedPk ? 'is-selected' : ''}">
        <td class="rank-cell">${p.tier_rank||''}</td>
        <td>
          <div class="person-cell">
            ${profileAvatar(p)}
            <div class="person-copy">
              <strong>@${escapeHtml(p.username||p.pk)}</strong>
              <span>${escapeHtml(p.full_name || i18nT('common.nameMissing', {}, 'Name unavailable'))}</span>
            </div>
          </div>
        </td>
        <td class="score-cell" title="${escapeAttr(scoreTitle)}">
          <div class="probability">
            <strong>${escapeHtml(scoreDisplay)}</strong>
            <span class="probability-track"><i style="width:${score == null ? 0 : score}%"></i></span>
          </div>
        </td>
        <td class="signal-cell">
          <span class="badge t-${tier}">${escapeHtml(tierLabel)}</span>
          ${flags ? `<div class="row-flags">${flags}</div>` : ''}
        </td>
        <td class="evidence-cell">${ev || '<span class="muted">—</span>'}</td>
      </tr>`);
  }
  tb.innerHTML = rows.join('');
  tb.querySelectorAll('tr').forEach(tr => {
    tr.addEventListener('click', () => selectPerson(tr.dataset.pk, {openDetail:true}));
  });
  translateUi(tb);
}

function personInitials(p) {
  const label = (p.full_name || p.username || '?').trim();
  return label.split(/\s+/).slice(0, 2)
    .map(part => part.charAt(0)).join('').toUpperCase() || '?';
}

function avatarProxyUrl(p, ownerUsername='') {
  const username = ownerUsername || (state.data && state.data.username) || state.username;
  const pk = p && p.pk;
  if (!username || !pk || !/^\d{1,30}$/.test(String(pk))) return '';
  return `/api/users/${encodeURIComponent(username)}/avatar/${encodeURIComponent(pk)}`;
}

let avatarWarmGeneration = 0;
function warmAvatarCache(data=state.data, ownerUsername='') {
                                                                              
                                                                     
  const generation = ++avatarWarmGeneration;
  const d = data;
  if (!d) return;
  const owner = ownerUsername || d.username || state.username;
  const targetIntel = d.target_intel || {};
  const targetUrl = (targetIntel.avatar || {}).profile_pic_url
    || (targetIntel.profile || {}).profile_pic_url || '';
  const queue = [
    {pk:String(d.target_pk || ''), profile_pic_url:targetUrl},
    ...(d.people || []),
  ].filter(p => p.profile_pic_url && /^\d{1,30}$/.test(String(p.pk || '')));
  let cursor = 0;
  const worker = async () => {
    while (generation === avatarWarmGeneration && cursor < queue.length) {
      const person = queue[cursor++];
      try {
        await fetch(avatarProxyUrl(person, owner), {cache:'force-cache'});
      } catch (_) {
                                                                       
      }
    }
  };
  Promise.all(Array.from({length:Math.min(2, queue.length)}, worker));
}

function profileAvatar(p, extraClass='') {
  const initials = personInitials(p);
  const avatarUrl = p.profile_pic_url ? avatarProxyUrl(p) : '';
  const image = avatarUrl
    ? `<img src="${escapeAttr(avatarUrl)}" alt="" loading="lazy"
         referrerpolicy="no-referrer" data-avatar-error="remove">`
    : '';
  return `<span class="person-avatar ${extraClass}" aria-hidden="true">
    <span>${escapeHtml(initials)}</span>${image}
  </span>`;
}

                                                                         
                                                                                  
document.addEventListener('error', event => {
  const image = event.target;
  if (!(image instanceof HTMLImageElement) || !image.dataset.avatarError) return;
  if (image.dataset.avatarError === 'hide') image.hidden = true;
  else if (image.dataset.avatarError === 'remove') image.remove();
}, true);

function canonicalTier(person) {
  const isRecord = Boolean(person && typeof person === 'object');
  const tier = String((isRecord ? (person.tier || person.hop_class) : person) || '').trim();
  const aliases = {
    intimate:'verified', known:'high_probability', acquaintance:'medium_probability',
    algorithmic:'low_probability',
  };
  if (tier === 'unknown' || (isRecord && !hasValidModelScore(person))) return 'unknown';
  if (aliases[tier]) return aliases[tier];
  if (['verified','high_probability','medium_probability','low_probability','noise','unknown'].includes(tier)) {
    return tier;
  }
  const score = isRecord ? modelScore(person) : null;
  if (score == null) return 'unknown';
  if (score >= 99) return 'verified';
  if (score >= 80) return 'high_probability';
  if (score >= 40) return 'medium_probability';
  if (score >= 15) return 'low_probability';
  return 'noise';
}

function localizedTierLabel(value, {short=false}={}) {
  const raw = typeof value === 'string' ? value : canonicalTier(value);
  const aliases = {
    intimate:'verified', known:'high_probability', acquaintance:'medium_probability',
    algorithmic:'low_probability',
  };
  const tier = aliases[raw] || raw;
  const keys = short ? {
    verified:'stats.veryHigh', high_probability:'stats.highShort',
    medium_probability:'stats.mediumShort', low_probability:'stats.lowShort', noise:'stats.weak',
    unknown:'tier.unknown',
  } : {
    verified:'stats.verified', high_probability:'stats.high',
    medium_probability:'stats.medium', low_probability:'stats.low', noise:'stats.noise',
    unknown:'tier.unknown',
  };
  return i18nT(keys[tier] || 'tier.unknown', {}, String(raw || '?').replace(/_/g, ' '));
}

function dashboardTierCounts() {
  const d = state.data || {people:[]};
  const fallback = (d.people || []).reduce((acc, person) => {
    const key = canonicalTier(person);
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const value = key => fallback[key] || 0;
  return {
    verified:value('verified'),
    high_probability:value('high_probability'),
    medium_probability:value('medium_probability'),
    low_probability:value('low_probability'),
                                                                                
    noise:value('noise') + value('unknown'),
    unknown:value('unknown'),
  };
}

function targetDashboardPerson() {
  const d = state.data || {};
  const ti = d.target_intel || {};
  const identity = ti.identity || {};
  const profile = ti.profile || {};
  const avatar = ti.avatar || {};
  return {
    pk:String(identity.pk || d.target_pk || ''),
    username:d.username || identity.username || state.username || '',
    full_name:identity.full_name || profile.full_name || '',
    profile_pic_url:avatar.profile_pic_url || profile.profile_pic_url || '',
    score:100,
    tier:'verified',
  };
}

function hasValidModelScore(person) {
  if (!person || typeof person !== 'object') return false;
  if (person.score_valid === false) return false;
  if (String(person.tier || '').toLowerCase() === 'unknown') return false;
  if (String(person.hop_class || '').toLowerCase() === 'unknown') return false;
  if (person.score == null || person.score === '') return false;
  return Number.isFinite(Number(person.score));
}

function modelScore(person) {
  if (!hasValidModelScore(person)) return null;
  return Math.max(0, Math.min(100, Number(person.score)));
}

function formatModelScore(person) {
  const score = modelScore(person);
  return score == null ? '—' : `${formatUiNumber(score, {maximumFractionDigits:1})}/100`;
}

function modelScoreDescription(person) {
  const score = modelScore(person);
  if (score == null) return i18nT('common.noValidScore', {}, 'No valid model score');
  const value = formatUiNumber(score, {maximumFractionDigits:1});
  return i18nT('common.modelScoreValue', {score:value}, `${value}/100 model score`);
}

function renderDashboardChrome() {
  const d = state.data;
  if (!d) return;
  const target = targetDashboardPerson();
  const ti = d.target_intel || {};
  const identity = ti.identity || {};
  const profile = ti.profile || {};
  const counts = dashboardTierCounts();

  $('#targetRailAvatar').innerHTML = profileAvatar(target, 'target-rail-photo');
  const meta = [];
  const rawAccountType = identity.account_type != null ? identity.account_type : profile.account_type;
  const business = typeof identity.is_business === 'boolean'
    ? identity.is_business
    : (typeof profile.is_business === 'boolean' ? profile.is_business : null);
  if (rawAccountType != null || business !== null) {
    const accountType = targetIntelAccountType({account_type:rawAccountType, is_business:business});
    if (accountType) meta.push(`${i18nT('report.accountType', {}, 'Account type')}: ${accountType}`);
  }
  if (business !== null) {
    meta.push(`${i18nT('target.businessLabel', {}, 'Business')}: ${i18nT(business ? 'common.yes' : 'common.no', {}, business ? 'Yes' : 'No')}`);
  }
  $('#targetRailMeta').innerHTML = meta.map(item => `<span>${escapeHtml(item)}</span>`).join('');
  $('#targetInstagramLink').href = `https://www.instagram.com/${encodeURIComponent(target.username)}/`;
  $('#targetThreadsLink').href = `https://www.threads.net/@${encodeURIComponent(target.username)}`;

  $('#targetSumVerified').textContent = counts.verified;
  $('#targetSumHigh').textContent = counts.high_probability;
  $('#targetSumMedium').textContent = counts.medium_probability;
  $('#targetSumLow').textContent = counts.low_probability;
  $('#targetSumNoise').textContent = counts.noise;
  $('#targetSumTotal').textContent = (d.people || []).length;
  $('#targetReportPreview').textContent = i18nT('panel.reportPreview', {
    username:`@${target.username}`, count:(d.people || []).length,
  }, `@${target.username} · ${(d.people || []).length} people\nModel confidence report`);
  $('#graphTotalMetric').textContent = (d.people || []).length;
  renderPeopleRail();
  translateUi($('#targetRail'));
}

function renderPeopleRail() {
  const d = state.data;
  const list = $('#peopleRailList');
  if (!d || !list) return;
  const minInput = $('#graphMinScore');
  const minScore = Math.max(0, Math.min(100, Number(minInput.value) || 0));
  const people = (d.people || [])
    .filter(person => {
      const score = modelScore(person);
      return score == null ? minScore === 0 : score >= minScore;
    })
    .slice()
    .sort((a, b) => (modelScore(b) ?? -1) - (modelScore(a) ?? -1)
      || Number(a.tier_rank || 0) - Number(b.tier_rank || 0)
      || compareUiText(String(a.username || ''), String(b.username || '')));
  const total = (d.people || []).length;
  $('#peopleRailCount').textContent = people.length === total ? `${total}` : `${people.length}/${total}`;
  list.innerHTML = people.map(person => {
    const tier = canonicalTier(person);
    const label = localizedTierLabel(tier, {short:true});
    const rowAria = i18nT('people.openPersonAria', {username:`@${person.username || person.pk}`}, `Open details for @${person.username || person.pk}`);
    return `<div class="rail-person t-${tier}${String(person.pk) === state.selectedPk ? ' is-selected' : ''}"
                 data-person-pk="${escapeAttr(person.pk)}" role="button" tabindex="0"
                 aria-label="${escapeAttr(rowAria)}">
      ${profileAvatar(person)}
      <div class="rail-person-copy">
        <strong>@${escapeHtml(person.username || person.pk)}</strong>
        <span>${escapeHtml(person.full_name || i18nT('common.nameMissing', {}, 'Name unavailable'))}</span>
      </div>
      <div class="rail-person-score" title="${escapeAttr(modelScoreDescription(person))}"><b>${escapeHtml(formatModelScore(person))}</b><small>${escapeHtml(label)}</small></div>
    </div>`;
  }).join('');
  list.querySelectorAll('.rail-person').forEach(row => {
    const select = () => selectPerson(row.dataset.personPk);
    const open = () => selectPerson(row.dataset.personPk, {openDetail:true});
    row.addEventListener('click', select);
    row.addEventListener('dblclick', open);
    row.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        open();
      }
    });
  });
  $('#peopleRailAll').innerHTML = `${escapeHtml(i18nT('people.viewAllCount', {count:total}, `View all ${total} people`))} <span>${uiIcon('chevron-right')}</span>`;
  translateUi(list);
}

function selectPerson(pk, options={}) {
  const key = String(pk || '');
  if (!key) return;
  state.selectedPk = key;
  syncPersonSelection();
  if (options.switchToGraph) activateTab('graph');
  if (options.openDetail) openDetail(key);
}

function syncPersonSelection(options={}) {
  const key = state.selectedPk;
  $$('#peopleBody tr[data-pk]').forEach(row => {
    row.classList.toggle('is-selected', Boolean(key && String(row.dataset.pk) === key));
  });
  $$('#peopleRailList [data-person-pk]').forEach(row => {
    const selected = Boolean(key && String(row.dataset.personPk) === key);
    row.classList.toggle('is-selected', selected);
    if (selected && options.scrollRail !== false) row.scrollIntoView({block:'nearest'});
  });
  let selectedNode = null;
  $$('#graphContainer [data-person-pk]').forEach(item => {
    const selected = Boolean(key && String(item.dataset.personPk) === key);
    item.classList.toggle('is-selected', selected);
    if (selected && item.classList.contains('node')) selectedNode = item;
  });
  if (selectedNode && selectedNode.parentNode) selectedNode.parentNode.appendChild(selectedNode);
  const graph = $('#graphContainer');
  const graphHasSelection = Boolean(key && $$('#graphContainer .node[data-person-pk]').some(node => String(node.dataset.personPk) === key));
  graph.classList.toggle('has-selection', graphHasSelection);
}

function personFlags(p) {
  const out = [];
  const hop = canonicalTier(p) === 'unknown' ? HOP_CLASS_FLAG.unknown : HOP_CLASS_FLAG[p.hop_class];
  if (hop) {
    out.push(`<span class="flag ${hop.cls}" title="${escapeAttr(i18nT(hop.titleKey, {}, 'Model confidence'))}">${uiIcon(hop.icon || 'info')}</span>`);
  }
  const inferred = String(p.inferred_relationship || '');
  if (['BIDIRECTIONAL_CHAIN_COOCCURRENCE','MUTUAL_FOLLOW'].includes(inferred)) {
    out.push(`<span class="flag STABLE" title="${escapeAttr(i18nT('flag.mutual', {}, 'Reciprocal recommendation overlap'))}">${uiIcon('arrow-left-right')}</span>`);
  } else if (['ONE_WAY_CHAIN_COOCCURRENCE','TARGET_FOLLOWS_X_ONLY'].includes(inferred)) {
    out.push(`<span class="flag HOP1" title="${escapeAttr(i18nT('flag.oneWay', {}, 'One-way recommendation-chain overlap'))}">${uiIcon('arrow-right')}</span>`);
  }
                                        
  if (p.banyan_view_count >= 3) {
    out.push(`<span class="flag STABLE" title="${escapeAttr(i18nT('flag.shareSuggestions', {count:p.banyan_view_count}, `Seen ${p.banyan_view_count} times in sharing suggestions`))}">${uiIcon('external-link')}<small>${p.banyan_view_count}</small></span>`);
  } else if (p.banyan_view_count >= 1) {
    out.push(`<span class="flag HOP1" title="${escapeAttr(i18nT('flag.shareSuggestions', {count:p.banyan_view_count}, `Seen ${p.banyan_view_count} times in sharing suggestions`))}">${uiIcon('external-link')}<small>${p.banyan_view_count}</small></span>`);
  }
  if (p.bootstrap_present) {
    const bs = p.bootstrap_max_score != null ? p.bootstrap_max_score : '?';
    const isBesties = (p.bootstrap_surfaces||[]).includes('coefficient_besties_list_ranking');
    const cls = isBesties ? 'STABLE' : 'HOP1';
    const lbl = isBesties
      ? `${uiIcon('star')}<small>${escapeHtml(i18nT('chip.closeFriend', {}, 'close friend'))}</small>`
      : `B${bs}`;
    const title = `Bootstrap: surfaces=${(p.bootstrap_surfaces||[]).join(',')||'-'} max_score=${bs} captures=${p.bootstrap_capture_count||0}`;
    out.push(`<span class="flag ${cls}" title="${title}">${lbl}</span>`);
  }
  if (p.is_private) out.push('<span class="flag P">P</span>');
  if (p.is_verified) out.push('<span class="flag V">V</span>');
  if (p.context_class === 'real_connection') out.push('<span class="flag R">R</span>');
  else if (p.context_class === 'suggested') out.push('<span class="flag S">S</span>');
  return out.join('');
}

function personEvidenceChips(p) {
  const chips = [];
  if (p.cluster_module_count) {
    const cls = p.cluster_module_count >= 11 ? 'strong' : '';
    chips.push(`<span class="evchip ${cls}">p28[${p.cluster_module_count}/15]</span>`);
  }
  if (p.likes_to_x.length || p.comments_to_x.length) {
    chips.push(`<span class="evchip">p29[L${p.likes_to_x.length}/C${p.comments_to_x.length}]</span>`);
  }
  if (p.tags_of_target_count) {
    chips.push(`<span class="evchip strong">tags=${p.tags_of_target_count}</span>`);
  }
  if (p.co_tag_count) {
    chips.push(`<span class="evchip">cotag=${p.co_tag_count}</span>`);
  }
  if (p.tag_search_hits) {
    chips.push(`<span class="evchip">ts=${p.tag_search_hits}</span>`);
  }
  if (p.news_events.length) {
    chips.push(`<span class="evchip">news=${p.news_events.length}</span>`);
  }
  if (p.mutual_followers_count) {
    chips.push(`<span class="evchip" title="${escapeAttr(i18nT('detail.viewerSharedFollowers', {}, 'Followers shared with the signed-in test account'))}">${escapeHtml(i18nT('chip.sharedFollowersTest', {count:p.mutual_followers_count}, `test shared: ${p.mutual_followers_count}`))}</span>`);
  }
  if (p.shared_locations.length) {
    chips.push(`<span class="evchip">loc=${p.shared_locations.length}</span>`);
  }
  if (p.evidence.some(e => e.source.startsWith('bidirectional'))) {
    chips.push(`<span class="evchip bidir">bidir</span>`);
  }
  if (p.evidence.some(e => e.source.startsWith('friendship_following'))) {
    chips.push(`<span class="evchip strong">→${escapeHtml(i18nT('chip.signedInFollows', {}, 'test account follows'))}</span>`);
  }
  if (p.evidence.some(e => e.source.startsWith('friendship_followed_by'))) {
    chips.push(`<span class="evchip strong">←${escapeHtml(i18nT('chip.followsSignedIn', {}, 'follows test account'))}</span>`);
  }
  if (p.evidence.some(e => e.source === 'phase32_suggested')) {
    chips.push(`<span class="evchip neg">${escapeHtml(i18nT('chip.suggested', {}, 'suggested'))}</span>`);
  }
  if (p.bootstrap_present) {
    const bs = p.bootstrap_max_score != null ? p.bootstrap_max_score : '?';
    const cap = p.bootstrap_capture_count || 1;
    chips.push(`<span class="evchip strong" title="bootstrap surfaces: ${(p.bootstrap_surfaces||[]).join(', ')||'-'}">boot=${bs}${cap>1?`×${cap}`:''}</span>`);
  }
  return chips.join('');
}

                                     
const DETAIL_CONFIDENCE_COPY = {
  verified: {
    labelKey:'detail.signalVeryHigh',
    textKey:'detail.signalVeryHighText',
  },
  high_probability: {
    labelKey:'detail.signalHigh',
    textKey:'detail.signalHighText',
  },
  medium_probability: {
    labelKey:'detail.signalMedium',
    textKey:'detail.signalMediumText',
  },
  low_probability: {
    labelKey:'detail.signalLow',
    textKey:'detail.signalLowText',
  },
  noise: {
    labelKey:'detail.signalInsufficient',
    textKey:'detail.signalNoneText',
  },
  unknown: {
    labelKey:'tier.unknown',
    textKey:'detail.signalUnknownText',
  },
};

function detailNumber(value) {
  return formatUiNumber(value);
}

function evidenceSignalDescriptor(source) {
  const name = String(source || '').toLowerCase();
  if (!name || name.startsWith('verification_')) return null;
  if (name === 'phase26_chaining_cluster') {
    return {key:'connection-cluster', icon:'network', title:'Bağlantı kümesi', text:'Bağlantı önerileri arasında görüldü.'};
  }
  if (name === 'phase28_stable_15_15') {
    return {key:'stable-surface', icon:'sparkles', title:'Tekrarlanan eşleşme', text:'Birçok analiz alanında tekrar görüldü.'};
  }
  if (name === 'phase32_real_top') {
    return {key:'repeated-discovery', icon:'signal-high', title:'Üst sıralarda', text:'Tekrarlı keşif sonuçlarında güçlü sırada çıktı.'};
  }
  if (name === 'phase32_real_mid') {
    return {key:'repeated-discovery', icon:'arrow-right', title:'Orta sıralarda', text:'Tekrarlı keşif sonuçlarında orta sırada çıktı.'};
  }
  if (name === 'phase32_real_tail') {
    return {key:'repeated-discovery', icon:'arrow-down-right', title:'Alt sıralarda', text:'Tekrarlı keşif sonuçlarında uzak sırada çıktı.'};
  }
  if (name === 'phase32_suggested') {
    return {key:'general-suggestion', icon:'search', title:'Genel öneri', text:'Yalnızca genel öneriler arasında görüldü.', tone:'weak'};
  }
  if (name.startsWith('bootstrap_')) {
    return {key:'instagram-suggestion', icon:'search', title:'Instagram önerisi', text:'Arama veya kişi önerileri arasında görüldü.'};
  }
  if (name.includes('bidirectional') || name.startsWith('phase35_')) {
    return {
      key:'reciprocal-chain', icon:'arrow-left-right',
      title:i18nT('detail.reciprocalSignal', {}, 'Reciprocal recommendation overlap'),
      text:i18nT('detail.reciprocalSignalText', {}, 'The candidate appeared in both directions of the recommendation-chain scan; this does not prove a follow.'),
    };
  }
  if (name.includes('following')) {
    return {
      key:'following-signal', icon:'arrow-right',
      title:i18nT('detail.viewerFollowInfo', {}, 'Signed-in test account follow status'),
      text:i18nT('detail.signedInFollowsAccount', {}, 'The signed-in test account follows this account.'),
    };
  }
  if (name.includes('followed_by')) {
    return {
      key:'followed-signal', icon:'arrow-left',
      title:i18nT('detail.viewerFollowInfo', {}, 'Signed-in test account follow status'),
      text:i18nT('detail.accountFollowsSignedIn', {}, 'This account follows the signed-in test account.'),
    };
  }
  if (name.includes('phase29_like') || name.includes('like')) {
    return {key:'likes', icon:'heart', title:'Beğeni etkileşimi', text:'Gönderilerde beğeni etkileşimi bulundu.'};
  }
  if (name.includes('phase29_comment') || name.includes('comment')) {
    return {key:'comments', icon:'message-circle', title:'Yorum etkileşimi', text:'Gönderilerde yorum etkileşimi bulundu.'};
  }
  if (name.includes('co_tag')) {
    return {key:'co-tags', icon:'tag', title:'Birlikte etiket', text:'Aynı içerikte birlikte etiketlendiler.'};
  }
  if (name.includes('phase30') || name.includes('tagger')) {
    return {key:'tags', icon:'tag', title:'Etiket etkileşimi', text:'Etiket üzerinden bir bağlantı izi bulundu.'};
  }
  if (name.includes('phase31') || name.includes('news')) {
    return {key:'notifications', icon:'bell', title:'Bildirim izi', text:'Bildirimlerde ortak bir etkileşim görüldü.'};
  }
  if (name.includes('phase37') || name.includes('banyan')) {
    return {key:'share-ranking', icon:'external-link', title:'Paylaşım önerisi', text:'Paylaşım sıralamasında görüldü.'};
  }
  return {key:'other-signal', icon:'info', title:'Destekleyici sinyal', text:'Analiz sırasında bir eşleşme bulundu.'};
}

function detailSignals(person) {
  const signals = new Map();
  const add = (key, signal, options={}) => {
    if (!key || !signal) return;
    const count = Number(options.count) || 1;
    const numericWeight = Number(options.weight);
    const hasWeight = options.weight != null && Number.isFinite(numericWeight);
    const current = signals.get(key);
    if (current) {
      current.count += count;
      if (hasWeight) current.weight = (current.weight || 0) + numericWeight;
      return;
    }
    signals.set(key, {
      ...signal,
      count,
      weight:hasWeight ? numericWeight : null,
      tone:options.tone || signal.tone || '',
    });
  };

  for (const evidence of (Array.isArray(person.evidence) ? person.evidence : [])) {
    if (!evidence) continue;
    const signal = evidenceSignalDescriptor(evidence.source);
    if (signal) add(signal.key, signal, {weight:evidence.weight});
  }

  const addCount = (key, count, icon, title, textKey, fallback) => {
    const total = Number(count) || 0;
    if (total <= 0 || signals.has(key)) return;
    add(key, {icon, title, text:i18nT(textKey, {count:total}, fallback.replace('{count}', detailNumber(total)))});
  };
  addCount('likes', (person.likes_to_x || []).length, 'heart', 'Beğeni etkileşimi', 'detail.likesFound', '{count} like records found.');
  addCount('comments', (person.comments_to_x || []).length, 'message-circle', 'Yorum etkileşimi', 'detail.commentsFound', '{count} comment records found.');
  addCount('tags', person.tags_of_target_count, 'tag', 'Etiket etkileşimi', 'detail.tagsFound', '{count} tagged items found.');
  addCount('co-tags', person.co_tag_count, 'tag', 'Birlikte etiket', 'detail.coTagsFound', '{count} co-tagged items found.');
  addCount('notifications', (person.news_events || []).length, 'bell', 'Bildirim izi', 'detail.interactionsFound', '{count} interaction records found.');
  addCount(
    'mutual-followers', person.mutual_followers_count, 'users',
    i18nT('detail.viewerSharedFollowers', {}, 'Followers shared with the signed-in test account'),
    'detail.mutualFollowersFound', '{count} followers shared with the signed-in test account.',
  );

  if (person.bootstrap_present && !signals.has('instagram-suggestion')) {
    add('instagram-suggestion', {icon:'search', title:'Instagram önerisi', text:'Instagram kişi önerileri arasında görüldü.'});
  }
  if (Number(person.banyan_view_count) > 0 && !signals.has('share-ranking')) {
    add('share-ranking', {
      icon:'external-link',
      title:'Paylaşım önerisi',
      text:i18nT('detail.shareRankingCount', {count:person.banyan_view_count}, `Seen ${detailNumber(person.banyan_view_count)} times in sharing rankings.`),
    });
  }
  const inferred = String(person.inferred_relationship || '');
  if (person.reciprocal_checked && ['BIDIRECTIONAL_CHAIN_COOCCURRENCE','MUTUAL_FOLLOW'].includes(inferred)) {
    add('reciprocal-chain', {
      icon:'arrow-left-right',
      title:i18nT('detail.reciprocalSignal', {}, 'Reciprocal recommendation overlap'),
      text:i18nT('detail.reciprocalSignalText', {}, 'The candidate appeared in both directions of the recommendation-chain scan; this does not prove a follow.'),
    });
  } else if (person.reciprocal_checked && ['ONE_WAY_CHAIN_COOCCURRENCE','TARGET_FOLLOWS_X_ONLY'].includes(inferred)) {
    add('reciprocal-chain', {
      icon:'arrow-right',
      title:i18nT('detail.oneWaySignal', {}, 'One-way recommendation-chain overlap'),
      text:i18nT('detail.oneWayTraceText', {}, 'The candidate appeared in only one direction of the recommendation-chain scan; this does not prove a follow.'),
    });
  }

  const friendship = person.friendship_status || {};
  if (friendship.following === true) {
    add('friendship-following', {
      icon:'arrow-left', title:i18nT('detail.viewerFollowInfo', {}, 'Signed-in test account follow status'),
      text:i18nT('detail.signedInFollowsAccount', {}, 'The signed-in test account follows this account.'),
    });
  }
  if (friendship.followed_by === true) {
    add('friendship-followed-by', {
      icon:'arrow-right', title:i18nT('detail.viewerFollowInfo', {}, 'Signed-in test account follow status'),
      text:i18nT('detail.accountFollowsSignedIn', {}, 'This account follows the signed-in test account.'),
    });
  }
  if (friendship.outgoing_request === true) {
    add('friendship-outgoing-request', {
      icon:'clock', title:i18nT('detail.viewerFollowRequest', {}, 'Signed-in test account follow request'),
      text:i18nT('detail.signedInRequestedAccount', {}, 'The signed-in test account sent this account a follow request.'),
    });
  }
  if (friendship.incoming_request === true) {
    add('friendship-incoming-request', {
      icon:'clock', title:i18nT('detail.viewerFollowRequest', {}, 'Signed-in test account follow request'),
      text:i18nT('detail.accountRequestedSignedIn', {}, 'This account sent the signed-in test account a follow request.'),
    });
  }
  if (friendship.is_bestie === true) {
    add('friendship-bestie', {
      icon:'star', title:i18nT('detail.viewerListStatus', {}, 'Signed-in test account list status'),
      text:i18nT('detail.inSignedInCloseFriends', {}, 'This account appears in the signed-in test account’s Close Friends list.'),
    });
  }
  if (friendship.is_feed_favorite === true) {
    add('friendship-favorite', {
      icon:'star', title:i18nT('detail.viewerListStatus', {}, 'Signed-in test account list status'),
      text:i18nT('detail.inSignedInFavorites', {}, 'This account appears in the signed-in test account’s Favorites feed.'),
    });
  }
  if (friendship.muting === true) {
    add('friendship-muted', {
      icon:'volume-x', title:i18nT('detail.viewerListStatus', {}, 'Signed-in test account list status'),
      text:i18nT('detail.mutedBySignedIn', {}, 'The signed-in test account appears to have muted this account.'), tone:'weak',
    });
  }
  if (friendship.blocking === true || friendship.is_restricted === true) {
    add('friendship-limited', {
      icon:'shield-alert', title:i18nT('detail.viewerListStatus', {}, 'Signed-in test account list status'),
      text:i18nT('detail.limitedBySignedIn', {}, 'The signed-in test account appears to have blocked or restricted this account.'), tone:'warning',
    });
  }

  return Array.from(signals.values()).sort((a, b) =>
    Math.abs(Number(b.weight) || 0) - Math.abs(Number(a.weight) || 0)
    || b.count - a.count);
}

function openDetail(pk) {
  const key = String(pk || '');
  const p = state.data.people.find(x => String(x.pk) === key);
  if (!p) return;
  state.selectedPk = key;
  syncPersonSelection({scrollRail:false});

  const tier = canonicalTier(p);
  const confidence = DETAIL_CONFIDENCE_COPY[tier] || DETAIL_CONFIDENCE_COPY.unknown;
  const score = modelScore(p);
  const scoreText = formatModelScore(p);
  const confidenceLabel = i18nT(confidence.labelKey, {}, localizedTierLabel(p));
  const confidenceText = i18nT(confidence.textKey, {}, i18nT('detail.signalUnknownText', {}, 'No valid model score was produced.'));
  $('#detailUsername').textContent = '@' + (p.username || '?');
  $('#detailPk').textContent = p.full_name || i18nT('detail.profileDetails', {}, 'Profile details');
  $('#detailTier').textContent = confidenceLabel;
  $('#detailTier').className = 'badge t-' + tier;
  $('#detailScore').textContent = score == null
    ? i18nT('common.noValidScore', {}, 'No valid model score')
    : modelScoreDescription(p);

  const body = [];
  const profileMeta = [];
  if (typeof p.is_private === 'boolean') {
    profileMeta.push(i18nT(p.is_private ? 'common.privateProfile' : 'common.publicProfile', {}, p.is_private ? 'Private profile' : 'Public profile'));
  }
  if (typeof p.is_verified === 'boolean') {
    profileMeta.push(i18nT(p.is_verified ? 'filter.blueTick' : 'common.noBlueTick', {}, p.is_verified ? 'Verified account' : 'No verification badge'));
  }
  body.push(`<section class="detail-identity-card">
    ${profileAvatar(p, 'detail-avatar')}
    <div class="detail-identity-copy">
      <span class="detail-eyebrow">Kişi özeti</span>
      <strong>${escapeHtml(p.full_name || '@' + (p.username || '?'))}</strong>
      <span>@${escapeHtml(p.username || '?')}</span>
      ${profileMeta.length ? `<small>${escapeHtml(profileMeta.join(' · '))}</small>` : ''}
    </div>
  </section>`);
  body.push(`<div class="links detail-links">
    <a href="https://www.instagram.com/${encodeURIComponent(p.username||'')}/" target="_blank" rel="noopener">Instagram ${uiIcon('external-link')}</a>
    <a href="https://www.threads.net/@${encodeURIComponent(p.username||'')}" target="_blank" rel="noopener">Threads ${uiIcon('external-link')}</a>
  </div>`);

  body.push(`<section class="detail-probability t-${tier}">
    <div class="detail-probability-head">
      <span>${escapeHtml(i18nT('detail.connectionProbability', {}, 'Model confidence'))}</span>
      <strong>${escapeHtml(scoreText)}</strong>
    </div>
    <div class="detail-probability-track" role="progressbar" aria-label="${escapeAttr(modelScoreDescription(p))}"
         aria-valuemin="0" aria-valuemax="100"${score == null ? '' : ` aria-valuenow="${score}"`}><i style="width:${score == null ? 0 : score}%"></i></div>
    <div class="detail-probability-copy">
      <b>${escapeHtml(confidenceLabel)}</b>
      <span>${escapeHtml(confidenceText)}</span>
    </div>
    <p>${escapeHtml(i18nT('detail.estimateDisclaimer', {}, 'This is an uncalibrated model-confidence score; it does not prove a follow, friendship, or real-world closeness.'))}</p>
  </section>`);

  const signals = detailSignals(p);
  body.push(`<section class="detail-section">
    <div class="detail-section-head">
      <div><span class="detail-eyebrow">Neden bu sonuç?</span><h3>Model güvenini etkileyen sinyaller</h3></div>
      <b>${signals.length}</b>
    </div>
    ${signals.length ? `<div class="detail-signal-grid">${signals.map(signal => {
      const meta = [];
      if (signal.count > 1) meta.push(i18nT('common.recordCount', {count:signal.count}, `${detailNumber(signal.count)} records`));
      if (signal.weight != null && signal.weight !== 0) {
        const value = `${signal.weight > 0 ? '+' : ''}${detailNumber(signal.weight)}`;
        meta.push(i18nT('detail.points', {value}, `${value} points`));
      }
      return `<article class="detail-signal-card ${signal.tone ? `is-${escapeAttr(signal.tone)}` : ''}">
        <div class="detail-signal-icon" aria-hidden="true">${uiIcon(signal.icon)}</div>
        <div class="detail-signal-copy">
          <span>Model sinyali</span>
          <strong>${escapeHtml(signal.title)}</strong>
          <p>${escapeHtml(signal.text)}</p>
          ${meta.length ? `<small>${escapeHtml(meta.join(' · '))}</small>` : ''}
        </div>
      </article>`;
    }).join('')}</div>` : '<p class="detail-empty">Ek model sinyali kaydedilmemiş.</p>'}
  </section>`);

  const facts = [];
  const addFact = (label, value) => {
    if (value == null || value === '') return;
    facts.push({label, value:String(value)});
  };
  if (typeof p.is_private === 'boolean') addFact('Profil', p.is_private ? 'Gizli' : 'Açık');
  if (typeof p.is_verified === 'boolean') addFact('Instagram rozeti', p.is_verified ? 'Var' : 'Yok');
  if (p.follower_count != null) addFact('Takipçi', detailNumber(p.follower_count));
  if (p.following_count != null) addFact('Takip', detailNumber(p.following_count));
  if (p.media_count != null) addFact('Paylaşım', detailNumber(p.media_count));
  if (Number(p.tier_rank) > 0) addFact('Analizdeki sıra', detailNumber(p.tier_rank));
  if (facts.length) {
    body.push(`<section class="detail-section detail-facts-section">
      <div class="detail-section-head"><div><span class="detail-eyebrow">Kısa bilgi</span><h3>Profil bilgileri</h3></div></div>
      <div class="detail-facts">${facts.map(fact => `<div><span>${escapeHtml(fact.label)}</span><b>${escapeHtml(fact.value)}</b></div>`).join('')}</div>
    </section>`);
  }

  $('#detailBody').innerHTML = body.join('');
  $('#detailPanel').classList.remove('hidden');
  translateUi($('#detailPanel'));
}

function closeDetail() {
  $('#detailPanel').classList.add('hidden');
}

                                           
function renderBootstrap() {
  const c = $('#bootstrapContent');
  const meta = (state.data?.meta?.sources?.bootstrap) || {};
  const cov = meta.coverage || {};
  const pool = state.data.people
    .filter(p => p.bootstrap_present)
    .sort((a, b) => {
                                              
      const ba = (a.bootstrap_surfaces||[]).includes('coefficient_besties_list_ranking') ? 1 : 0;
      const bb = (b.bootstrap_surfaces||[]).includes('coefficient_besties_list_ranking') ? 1 : 0;
      if (ba !== bb) return bb - ba;
      return (b.bootstrap_max_score||0) - (a.bootstrap_max_score||0);
    });

  if (!meta.loaded) {
    c.innerHTML = `<p class="muted">${escapeHtml(i18nT('signals.noCapture', {}, 'No saved suggestion data was found for this analysis.'))}</p>`;
    translateUi(c);
    return;
  }

  const captures = meta.captures_loaded || [];
  const surfacesSeen = meta.surfaces_with_scores || {};
  const meets = cov.coverage_meets_target;
  const covLine = (cov.coverage_pct != null)
    ? `<span class="badge ${meets ? 't-verified' : 't-low_probability'}">
         ${escapeHtml(i18nT('signals.coverage', {
           coverage:formatUiPercent(cov.coverage_pct, {maximumFractionDigits:1}),
           target:formatUiPercent(cov.coverage_target_pct, {maximumFractionDigits:1}),
         }, `Coverage ${cov.coverage_pct}% / target ${cov.coverage_target_pct}%`))}
       </span>`
    : `<span class="muted">${escapeHtml(i18nT('signals.coverageUnknown', {}, 'Coverage cannot be calculated because the target follower count is unavailable.'))}</span>`;
  const warn = cov.warning ? `<div class="alt-row no-i18n" style="background:#3a1a1a;color:#f9a">${escapeHtml(cov.warning)}</div>` : '';

  const surfaceRows = Object.entries(surfacesSeen).map(([n, c]) =>
    `<li><code>${escapeHtml(n)}</code> — ${escapeHtml(i18nT('signals.captureCount', {count:c}, `${c} captures`))}</li>`).join('');

  const rows = pool.map(p => {
    const surfList = (p.bootstrap_surfaces||[]).map(s => {
      const short = s.replace('coefficient_','').replace('_ranking','').replace('_list','');
      return `<span class="evchip">${escapeHtml(short)}</span>`;
    }).join('');
    const isBestie = (p.bootstrap_surfaces||[]).includes('coefficient_besties_list_ranking');
    return `
      <tr data-pk="${p.pk}">
        <td>${isBestie ? uiIcon('star') : ''}</td>
        <td class="mono no-i18n">@${escapeHtml(p.username||'?')}</td>
        <td class="no-i18n">${escapeHtml(p.full_name||'')}</td>
        <td>${p.is_private?'<span class="flag P">P</span>':''} ${p.is_verified?'<span class="flag V">V</span>':''}</td>
        <td class="score-cell">${p.bootstrap_max_score!=null?p.bootstrap_max_score:'?'}</td>
        <td>${p.bootstrap_capture_count||1}</td>
        <td>${surfList}</td>
        <td class="score-cell" title="${escapeAttr(modelScoreDescription(p))}">${escapeHtml(formatModelScore(p))}</td>
      </tr>`;
  }).join('');

  c.innerHTML = `
    <div class="filters" style="gap:1em;margin-bottom:.7em">
      ${covLine}
      <span class="muted">${escapeHtml(i18nT('signals.pool', {count:meta.unique_pks || 0}, `Pool: ${meta.unique_pks || 0} people`))}</span>
      <span class="muted">${escapeHtml(i18nT('signals.captures', {count:meta.captures_count || 0}, `Captures: ${meta.captures_count || 0}`))}</span>
    </div>
    ${warn}
    ${captures.length ? `<details style="margin-bottom:.7em"><summary class="muted">${escapeHtml(i18nT('signals.captureFiles', {count:captures.length}, `Capture files (${captures.length})`))}</summary><ul class="muted mono no-i18n">${captures.map(f=>`<li>${escapeHtml(f)}</li>`).join('')}</ul></details>` : ''}
    ${surfaceRows ? `<details style="margin-bottom:.7em"><summary class="muted">${escapeHtml(i18nT('signals.surfacesSeen', {}, 'Sources seen'))}</summary><ul class="muted">${surfaceRows}</ul></details>` : ''}
    <div class="table-wrap">
      <table id="bootstrapTable">
        <thead><tr>
          <th title="${escapeAttr(i18nT('signals.bestieTitle', {}, 'Found in Close Friends suggestions'))}">${uiIcon('star')}</th>
          <th>${escapeHtml(i18nT('signals.username', {}, 'Username'))}</th>
          <th>${escapeHtml(i18nT('signals.fullName', {}, 'Full name'))}</th>
          <th>${escapeHtml(i18nT('signals.flags', {}, 'Flags'))}</th>
          <th title="${escapeAttr(i18nT('signals.coefficientTitle', {}, 'Instagram coefficient (0–100)'))}">${escapeHtml(i18nT('signals.score', {}, 'Score'))}</th>
          <th title="${escapeAttr(i18nT('signals.captureAppearances', {}, 'Number of captures containing this account'))}">×</th>
          <th>${escapeHtml(i18nT('signals.sources', {}, 'Sources'))}</th>
          <th title="${escapeAttr(i18nT('signals.finalProbability', {}, 'Final model-confidence score'))}">${escapeHtml(i18nT('table.probability', {}, 'Model score'))}</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
  c.querySelectorAll('#bootstrapTable tbody tr').forEach(tr => {
    tr.addEventListener('click', () => openDetail(tr.dataset.pk));
  });
  translateUi(c);
}

                                                                     
function legacyDrawGraph() {
  const container = $('#graphContainer');
  container.innerHTML = '';
  if (!state.data) return;

  const minScore = parseInt($('#graphMinScore').value || '20', 10);
  const nodes = state.data.people
    .filter(p => modelScore(p) != null && modelScore(p) >= minScore)
    .sort((a, b) => modelScore(b) - modelScore(a));
  $('#graphStats').textContent =
    `${nodes.length} kullanıcı · güçlü sinyaller merkeze daha yakın · sürükle/kaydır, tekerlekle yakınlaş`;
  if (!nodes.length) {
    container.innerHTML = '<p class="muted graph-empty">Bu eşikte kullanıcı yok.</p>';
    return;
  }

  const NS = 'http://www.w3.org/2000/svg';
  const svgEl = (name, attrs={}) => {
    const el = document.createElementNS(NS, name);
    for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
    return el;
  };

                                                                         
                                                                              
  const virtualSize = Math.max(1400, Math.ceil(Math.sqrt(nodes.length)) * 210);
  const W = Math.max(container.clientWidth || 1100, virtualSize);
  const H = Math.max(container.clientHeight || 820, virtualSize);
  const size = Math.min(W, H);
  const cx = W / 2;
  const cy = H / 2;
  const svg = svgEl('svg', {viewBox:`0 0 ${W} ${H}`, width:W, height:H});
  svg.setAttribute('aria-label', 'Sinyal gücüne göre Instagram ilişki grafiği');
  container.appendChild(svg);

  const defs = svgEl('defs');
  const filter = svgEl('filter', {id:'nodeGlow', x:'-80%', y:'-80%', width:'260%', height:'260%'});
  filter.appendChild(svgEl('feGaussianBlur', {stdDeviation:'3', result:'blur'}));
  const merge = svgEl('feMerge');
  merge.appendChild(svgEl('feMergeNode', {in:'blur'}));
  merge.appendChild(svgEl('feMergeNode', {in:'SourceGraphic'}));
  filter.appendChild(merge);
  defs.appendChild(filter);
  svg.appendChild(defs);

  const viewport = svgEl('g', {class:'graph-viewport'});
  svg.appendChild(viewport);

  const bands = [
    {key:'verified', label:'Çok yüksek güven · skor 99–100', min:size*.070, max:size*.195, color:'#ff6b9d', test:s=>s>=99},
    {key:'high', label:'Yüksek güven · skor 80–98,9', min:size*.250, max:size*.335, color:'#ffcf66', test:s=>s>=80},
    {key:'medium', label:'Orta güven · skor 40–79,9', min:size*.400, max:size*.400, color:'#61dafb', test:s=>s>=40},
    {key:'low', label:'Düşük güven · skor 0–39,9', min:size*.455, max:size*.455, color:'#718096', test:s=>s>=0},
  ];
  const bandFor = score => bands.find(b => b.test(score)) || bands[bands.length - 1];

                                                                   
  const guides = svgEl('g', {class:'signal-rings'});
  for (const band of bands) {
    guides.appendChild(svgEl('circle', {
      cx, cy, r:band.max, fill:'none', stroke:band.color,
      'stroke-opacity':'0.18', 'stroke-width':'1'
    }));
    const label = svgEl('text', {
      x:cx + 10, y:cy - band.max + 16, fill:band.color,
      'text-anchor':'start', class:'ring-label'
    });
    label.textContent = band.label;
    guides.appendChild(label);
  }
  viewport.appendChild(guides);

                                                                              
  const grouped = new Map(bands.map(b => [b.key, []]));
  for (const person of nodes) grouped.get(bandFor(modelScore(person)).key).push(person);
  const positions = new Map();
                                                                        
  const nodeSpacing = 175;
  const laneGap = 110;
  for (const band of bands) {
    const people = grouped.get(band.key);
    let cursor = 0;
    let lane = 0;
    while (cursor < people.length) {
      const radius = Math.min(band.min + lane * laneGap, band.max);
      const capacity = Math.max(4, Math.floor((Math.PI * 2 * radius) / nodeSpacing));
      const count = Math.min(capacity, people.length - cursor);
      for (let i = 0; i < count; i++) {
        const angle = (i / count) * Math.PI * 2 - Math.PI / 2 + lane * 0.23;
        const person = people[cursor + i];
        positions.set(person.pk, {
          x:cx + radius * Math.cos(angle),
          y:cy + radius * Math.sin(angle),
          p:person,
          color:band.color,
        });
      }
      cursor += count;
      lane += 1;
    }
  }

  const edges = svgEl('g', {class:'graph-edges'});
  for (const pos of positions.values()) {
    const score = modelScore(pos.p) ?? 0;
    edges.appendChild(svgEl('line', {
      class:'edge', x1:cx, y1:cy, x2:pos.x, y2:pos.y,
      'stroke-width':String(0.45 + score / 90),
      'stroke-opacity':String(0.08 + score / 650)
    }));
  }
  viewport.appendChild(edges);

  const addPhotoNode = ({person, x, y, color, radius, target=false}) => {
    const group = svgEl('g', {
      class:`node${target ? ' target' : ''}`,
      transform:`translate(${x},${y})`,
      tabindex:'0', role:'button'
    });
    const score = modelScore(person) ?? 0;
    const halo = svgEl('circle', {
      r:radius + 4, fill:'rgba(9,12,20,.94)', stroke:color,
      'stroke-width':target ? '3.5' : String(1.8 + score / 55),
      class:'node-halo'
    });
    if (score >= 99 || target) halo.setAttribute('filter', 'url(#nodeGlow)');
    group.appendChild(halo);
    group.appendChild(svgEl('circle', {r:radius, fill:'#202638', class:'node-base'}));

    const initials = svgEl('text', {
      'text-anchor':'middle', y:'1', dy:'.35em', class:'node-initials'
    });
    initials.textContent = personInitials(person);
    group.appendChild(initials);

    const proxyUrl = person.profile_pic_url ? avatarProxyUrl(person) : '';
    if (proxyUrl) {
      const clipId = `avatarClip-${String(person.pk || 'target').replace(/[^a-zA-Z0-9_-]/g, '')}`;
      const clip = svgEl('clipPath', {id:clipId});
      clip.appendChild(svgEl('circle', {cx:'0', cy:'0', r:String(radius - 1)}));
      defs.appendChild(clip);
      const image = svgEl('image', {
        href:proxyUrl,
        x:String(-radius), y:String(-radius),
        width:String(radius * 2), height:String(radius * 2),
        preserveAspectRatio:'xMidYMid slice',
        'clip-path':`url(#${clipId})`
      });
      image.addEventListener('error', () => image.remove());
      group.appendChild(image);
    }

    const username = `@${person.username || person.pk || '?'}`.slice(0, 22);
    const labelWidth = Math.max(52, username.length * 6.4 + 14);
    group.appendChild(svgEl('rect', {
      x:String(-labelWidth/2), y:String(radius + 8), width:String(labelWidth),
      height:'20', rx:'10', class:'node-label-bg'
    }));
    const label = svgEl('text', {
      'text-anchor':'middle', y:String(radius + 22), class:'node-label'
    });
    label.textContent = username;
    group.appendChild(label);

    const title = svgEl('title');
    title.textContent = target
      ? `Hedef: @${person.username || '?'}`
      : `@${person.username || '?'} · ${modelScoreDescription(person)} · ${localizedTierLabel(person)}`;
    group.appendChild(title);
    if (!target) {
      group.addEventListener('click', () => openDetail(person.pk));
      group.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') openDetail(person.pk);
      });
    }
    viewport.appendChild(group);
  };

  const targetIntel = state.data.target_intel || {};
  const targetAvatar = (targetIntel.avatar || {}).profile_pic_url
    || (targetIntel.profile || {}).profile_pic_url || '';
  addPhotoNode({
    person:{pk:String(state.data.target_pk || ''), username:state.data.username, full_name:'Hedef',
      profile_pic_url:targetAvatar, score:100},
    x:cx, y:cy, color:'#ffffff', radius:30, target:true
  });
  for (const pos of positions.values()) {
    const radius = 16 + Math.min(5, (modelScore(pos.p) ?? 0) / 30);
    addPhotoNode({person:pos.p, x:pos.x, y:pos.y, color:pos.color, radius});
  }

                                                         
  requestAnimationFrame(() => {
    container.scrollLeft = Math.max(0, (W - container.clientWidth) / 2);
    container.scrollTop = Math.max(0, (H - container.clientHeight) / 2);
  });

                                
  let vbX=0, vbY=0, vbW=W, vbH=H;
  let dragging=false, startX=0, startY=0;
  svg.addEventListener('wheel', e => {
    e.preventDefault();
    const factor = e.deltaY > 0 ? 1.14 : 0.88;
    const mx = e.offsetX / svg.clientWidth * vbW + vbX;
    const my = e.offsetY / svg.clientHeight * vbH + vbY;
    vbW *= factor; vbH *= factor;
    vbX = mx - e.offsetX / svg.clientWidth * vbW;
    vbY = my - e.offsetY / svg.clientHeight * vbH;
    svg.setAttribute('viewBox', `${vbX} ${vbY} ${vbW} ${vbH}`);
  }, {passive:false});
  svg.addEventListener('mousedown', e => {
    if (e.target.closest && e.target.closest('.node')) return;
    dragging=true; startX=e.clientX; startY=e.clientY;
  });
  window.addEventListener('mouseup', () => dragging=false);
  window.addEventListener('mousemove', e => {
    if (!dragging) return;
    vbX -= (e.clientX-startX) * vbW/svg.clientWidth;
    vbY -= (e.clientY-startY) * vbH/svg.clientHeight;
    startX=e.clientX; startY=e.clientY;
    svg.setAttribute('viewBox', `${vbX} ${vbY} ${vbW} ${vbH}`);
  });
}

                                                                                    
function drawGraph() {
  const container = $('#graphContainer');
  container.innerHTML = '';
  container.classList.remove('has-selection');
  state.graphController = null;
  if (!state.data) return;

  const minInput = $('#graphMinScore');
  const minScore = Math.max(0, Math.min(100, Number(minInput.value) || 0));
  minInput.value = String(minScore);
  const mobileMin = $('#graphMinScoreMobile');
  if (mobileMin && document.activeElement !== mobileMin) mobileMin.value = String(minScore);

  const tierOrder = {
    verified:0, high_probability:1, medium_probability:2,
    low_probability:3, noise:4,
  };
  const nodes = (state.data.people || [])
    .filter(person => {
      const score = modelScore(person);
      return score != null && score >= minScore;
    })
    .slice()
    .sort((a, b) => tierOrder[canonicalTier(a)] - tierOrder[canonicalTier(b)]
      || (modelScore(b) ?? -1) - (modelScore(a) ?? -1)
      || Number(a.tier_rank || 0) - Number(b.tier_rank || 0)
      || compareUiText(String(a.pk || ''), String(b.pk || '')));

  $('#graphStats').textContent = i18nT('graph.instructions', {
    count:nodes.length,
  }, `${nodes.length} people · stronger signals are closer to the center · select, open details, drag or zoom`);
  $('#graphVisibleMetric').textContent = formatUiNumber(nodes.length);
  $('#graphTotalMetric').textContent = formatUiNumber(state.data.people.length);
  $('#graphMinMetric').textContent = formatUiNumber(minScore);

  const NS = 'http://www.w3.org/2000/svg';
  const W = 1000;
  const H = 560;
  const cx = W / 2;
                                                                               
  const cy = 258;
  const targetRadius = 36;
  const svgEl = (name, attrs={}) => {
    const element = document.createElementNS(NS, name);
    for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, String(value));
    return element;
  };

  const svg = svgEl('svg', {
    viewBox:`0 0 ${W} ${H}`,
    role:'group',
    'aria-label':i18nT('graph.aria', {}, 'Instagram relationship graph arranged by signal strength'),
    preserveAspectRatio:'xMidYMid meet',
  });
  container.appendChild(svg);

  const defs = svgEl('defs');
  const glow = svgEl('filter', {id:'nodeGlow', x:'-80%', y:'-80%', width:'260%', height:'260%'});
  glow.appendChild(svgEl('feGaussianBlur', {stdDeviation:'2.4', result:'blur'}));
  const glowMerge = svgEl('feMerge');
  glowMerge.appendChild(svgEl('feMergeNode', {in:'blur'}));
  glowMerge.appendChild(svgEl('feMergeNode', {in:'SourceGraphic'}));
  glow.appendChild(glowMerge);
  defs.appendChild(glow);
  svg.appendChild(defs);

  const viewport = svgEl('g', {class:'graph-viewport'});
  const guideLayer = svgEl('g', {class:'signal-rings'});
  const edgeLayer = svgEl('g', {class:'graph-edges'});
  const nodeLayer = svgEl('g', {class:'graph-nodes'});
  viewport.appendChild(guideLayer);
  viewport.appendChild(edgeLayer);
  viewport.appendChild(nodeLayer);
  svg.appendChild(viewport);

  const bands = [
    {key:'verified', color:'#29d9ff'},
    {key:'high_probability', color:'#ff438d'},
    {key:'medium_probability', color:'#ffad3d'},
    {key:'low_probability', color:'#398dff'},
    {key:'noise', color:'#9954e8'},
  ];
  const grouped = new Map(bands.map(band => [band.key, []]));
  for (const person of nodes) grouped.get(canonicalTier(person)).push(person);

  const makeLayout = nodeRadius => {
    const positions = [];
    const lanes = [];
    const spacing = nodeRadius * 2 + 4;
    const laneStep = nodeRadius * 2 + 14;
    const projectedScale = nodes.length <= 130 ? 1.10 : 1;
    let radius = targetRadius + nodeRadius + 36;
    let laneIndex = 0;
    for (let bandIndex = 0; bandIndex < bands.length; bandIndex++) {
      const band = bands[bandIndex];
      const people = grouped.get(band.key);
      const laneSpecs = [];
      let totalCapacity = 0;
      while (totalCapacity < people.length) {
        const firstLane = laneIndex === 0 && laneSpecs.length === 0;
        const needsCurveClearance = !firstLane
          && cy - radius * projectedScale - (nodeRadius + 6) < 52;
        const exclusion = firstLane ? 1.8 : (needsCurveClearance ? .90 : 0);
        const gapCenter = firstLane ? Math.PI / 2 : -Math.PI / 2;
        const usableArc = Math.PI * 2 - exclusion;
        const capacity = Math.max(8, Math.floor((usableArc * radius) / spacing));
        laneSpecs.push({radius, capacity, exclusion, usableArc, gapCenter});
        totalCapacity += capacity;
        radius += laneStep;
      }
      let cursor = 0;
      for (let specIndex = 0; specIndex < laneSpecs.length; specIndex++) {
        const spec = laneSpecs[specIndex];
        const lanesRemaining = laneSpecs.length - specIndex;
        const count = Math.min(spec.capacity, Math.ceil((people.length - cursor) / lanesRemaining));
        const phase = -Math.PI / 2 + laneIndex * 0.29 + bandIndex * 0.11;
        lanes.push({radius:spec.radius, color:band.color, key:band.key});
        for (let i = 0; i < count; i++) {
          const angle = spec.exclusion
            ? spec.gapCenter + spec.exclusion / 2 + ((i + .5) / count) * spec.usableArc
            : phase + (i / count) * Math.PI * 2;
          positions.push({
            person:people[cursor + i],
            x:cx + spec.radius * Math.cos(angle),
            y:cy + spec.radius * Math.sin(angle),
            color:band.color,
            tier:band.key,
          });
        }
        cursor += count;
        laneIndex += 1;
      }
    }
    return {positions, lanes, nodeRadius, maxRadius:lanes.length ? lanes[lanes.length - 1].radius : 0};
  };

  let layout = makeLayout(10);
  for (const candidate of [10, 9, 8, 7, 6]) {
    const attempt = makeLayout(candidate);
    layout = attempt;
    if (attempt.maxRadius + candidate <= 252) break;
  }

                                                                            
                                                                             
                                                                            
  const radialScale = nodes.length <= 130 && layout.maxRadius > 0
    ? Math.max(1, Math.min(1.10, 238 / layout.maxRadius))
    : 1;
  if (radialScale > 1) {
    for (const position of layout.positions) {
      position.x = cx + (position.x - cx) * radialScale;
      position.y = cy + (position.y - cy) * radialScale;
    }
    for (const lane of layout.lanes) lane.radius *= radialScale;
    layout.maxRadius *= radialScale;
  }

                                                                     
  const topExtent = layout.maxRadius + layout.nodeRadius + 10;
  const bottomExtent = layout.maxRadius + layout.nodeRadius + 24;
  const viewPad = 12;
  const minY = cy - topExtent;
  const maxY = cy + bottomExtent;
  const viewY = Math.min(0, minY - viewPad);
  const viewBottom = Math.max(H, maxY + viewPad);
  const viewHeight = viewBottom - viewY;
  const viewWidth = Math.max(W, viewHeight * W / H);
  const baseView = {
    x:cx - viewWidth / 2, y:viewY,
    w:viewWidth, h:viewHeight,
  };
  svg.setAttribute('viewBox', `${baseView.x} ${baseView.y} ${baseView.w} ${baseView.h}`);

  guideLayer.appendChild(svgEl('circle', {
    cx, cy, r:targetRadius + 14, class:'ring-guide',
    stroke:'#29d9ff', 'stroke-opacity':'.16',
  }));
  for (const lane of layout.lanes) {
    guideLayer.appendChild(svgEl('circle', {
      cx, cy, r:lane.radius, class:'ring-guide',
      stroke:lane.color, 'stroke-opacity':'.19', 'data-tier':lane.key,
    }));
  }

  for (const position of layout.positions) {
    const score = modelScore(position.person) ?? 0;
    const edge = svgEl('line', {
      class:`edge${String(position.person.pk) === state.selectedPk ? ' is-selected' : ''}`,
      x1:cx, y1:cy, x2:position.x, y2:position.y,
      'data-person-pk':position.person.pk,
      'stroke-width':Math.max(.55, Math.min(1.25, .45 + score / 125)),
      'stroke-opacity':Math.max(.08, Math.min(.24, .07 + score / 650)),
      style:`--edge-accent:${position.color}`,
    });
    edgeLayer.appendChild(edge);
  }

  const addPhotoNode = ({person, x, y, color, radius, target=false, tier=''}) => {
    const key = String(person.pk || '');
    const selected = !target && key === state.selectedPk;
    const group = svgEl('g', {
      class:`node${target ? ' target' : ''}${selected ? ' is-selected' : ''}`,
      transform:`translate(${x},${y})`,
      tabindex:target ? '-1' : '0',
      role:target ? 'img' : 'button',
      'aria-label':target
        ? i18nT('graph.targetAria', {username:`@${person.username || '?'}`}, `Target @${person.username || '?'}`)
        : i18nT('graph.personAria', {
            username:`@${person.username || person.pk || '?'}`,
            score:modelScoreDescription(person),
          }, `@${person.username || person.pk || '?'}, ${modelScoreDescription(person)}`),
    });
    if (!target) group.setAttribute('data-person-pk', key);

    const score = modelScore(person) ?? 0;
    const halo = svgEl('circle', {
      r:radius + (target ? 4 : 2),
      fill:'rgba(4,12,23,.96)',
      stroke:color,
      'stroke-width':target ? 3 : Math.max(1.5, Math.min(2.5, 1.2 + score / 90)),
      class:'node-halo',
    });
    if (target || score >= 99) halo.setAttribute('filter', 'url(#nodeGlow)');
    group.appendChild(halo);
    group.appendChild(svgEl('circle', {r:radius, fill:'#16263a', class:'node-base'}));

    const initials = svgEl('text', {
      'text-anchor':'middle', y:'1', dy:'.35em', class:'node-initials',
    });
    initials.textContent = personInitials(person);
    group.appendChild(initials);

    const proxyUrl = person.profile_pic_url ? avatarProxyUrl(person) : '';
    if (proxyUrl) {
      const safeKey = key.replace(/[^a-zA-Z0-9_-]/g, '') || 'unknown';
      const clipId = `radialAvatar-${target ? 'target-' : ''}${safeKey}`;
      const clip = svgEl('clipPath', {id:clipId});
      clip.appendChild(svgEl('circle', {cx:0, cy:0, r:radius - 1}));
      defs.appendChild(clip);
      const image = svgEl('image', {
        href:proxyUrl, x:-radius, y:-radius,
        width:radius * 2, height:radius * 2,
        preserveAspectRatio:'xMidYMid slice',
        'clip-path':`url(#${clipId})`,
      });
      image.addEventListener('error', () => image.remove());
      group.appendChild(image);
    }

    const username = `@${person.username || person.pk || '?'}`.slice(0, target ? 28 : 22);
    const labelWidth = Math.max(target ? 92 : 48, username.length * (target ? 7.1 : 5.7) + 14);
    group.appendChild(svgEl('rect', {
      x:-labelWidth / 2, y:radius + (target ? 8 : 6), width:labelWidth,
      height:target ? 22 : 17, rx:target ? 7 : 6, class:'node-label-bg',
    }));
    const label = svgEl('text', {
      'text-anchor':'middle', y:radius + (target ? 23 : 18), class:'node-label',
    });
    label.textContent = username;
    group.appendChild(label);
    if (target) {
      const subLabel = svgEl('text', {
        'text-anchor':'middle', y:radius + 39, class:'target-sub-label',
      });
      subLabel.textContent = `pk=${person.pk || '?'}`;
      group.appendChild(subLabel);
    }

    const title = svgEl('title');
    title.textContent = target
      ? i18nT('graph.targetTitle', {
          username:`@${person.username || '?'}`, pk:person.pk || '?',
        }, `Target: @${person.username || '?'} (pk=${person.pk || '?'})`)
      : `@${person.username || '?'}${person.full_name ? ` | ${person.full_name}` : ''} | ${modelScoreDescription(person)} | ${localizedTierLabel(person)}`;
    group.appendChild(title);
    if (!target) {
      const select = event => {
        event.preventDefault();
        event.stopPropagation();
        selectPerson(key);
      };
      const open = event => {
        event.preventDefault();
        event.stopPropagation();
        selectPerson(key, {openDetail:true});
      };
      group.addEventListener('click', select);
      group.addEventListener('dblclick', open);
      group.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') open(event);
      });
    }
    nodeLayer.appendChild(group);
  };

  for (const position of layout.positions) {
    addPhotoNode({
      person:position.person, x:position.x, y:position.y,
      color:position.color, radius:layout.nodeRadius, tier:position.tier,
    });
  }
  addPhotoNode({
    person:targetDashboardPerson(), x:cx, y:cy,
    color:'#eaf8ff', radius:targetRadius, target:true, tier:'target',
  });

  let view = {...baseView};
  let drag = null;
  const applyView = () => svg.setAttribute('viewBox', `${view.x} ${view.y} ${view.w} ${view.h}`);
  const worldPoint = (clientX, clientY) => {
    const point = svg.createSVGPoint();
    point.x = clientX;
    point.y = clientY;
    const matrix = svg.getScreenCTM();
    return matrix ? point.matrixTransform(matrix.inverse()) : {x:cx, y:cy};
  };
  const zoomAt = (factor, clientX=null, clientY=null) => {
    const anchor = clientX == null ? {x:view.x + view.w / 2, y:view.y + view.h / 2} : worldPoint(clientX, clientY);
    const ratioX = (anchor.x - view.x) / view.w;
    const ratioY = (anchor.y - view.y) / view.h;
    const nextW = Math.max(baseView.w * .32, Math.min(baseView.w * 2.25, view.w * factor));
    const actualFactor = nextW / view.w;
    const nextH = view.h * actualFactor;
    view = {
      x:anchor.x - ratioX * nextW,
      y:anchor.y - ratioY * nextH,
      w:nextW,
      h:nextH,
    };
    applyView();
  };
  const fit = () => {
    view = {...baseView};
    applyView();
  };
  state.graphController = {zoomBy:zoomAt, fit};

  svg.addEventListener('wheel', event => {
    event.preventDefault();
    zoomAt(event.deltaY > 0 ? 1.12 : .88, event.clientX, event.clientY);
  }, {passive:false});
  svg.addEventListener('pointerdown', event => {
    if (event.target.closest && event.target.closest('.node')) return;
    drag = {pointerId:event.pointerId, x:event.clientX, y:event.clientY, view:{...view}};
    svg.setPointerCapture(event.pointerId);
  });
  svg.addEventListener('pointermove', event => {
    if (!drag || drag.pointerId !== event.pointerId) return;
    const rect = svg.getBoundingClientRect();
    view.x = drag.view.x - (event.clientX - drag.x) * drag.view.w / Math.max(1, rect.width);
    view.y = drag.view.y - (event.clientY - drag.y) * drag.view.h / Math.max(1, rect.height);
    applyView();
  });
  const endDrag = event => {
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (svg.hasPointerCapture(event.pointerId)) svg.releasePointerCapture(event.pointerId);
    drag = null;
  };
  svg.addEventListener('pointerup', endDrag);
  svg.addEventListener('pointercancel', endDrag);
  svg.addEventListener('lostpointercapture', () => { drag = null; });
  syncPersonSelection({scrollRail:false});
  translateUi(container);
}

                                
function escapeHtml(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function escapeAttr(s) {
  return escapeHtml(s).replace(/`/g, '&#96;');
}

function activateTab(name) {
  const panel = $('#tab-' + name);
  const tab = $(`.tab[data-tab="${name}"]`);
  if (!panel || !tab) return;
  $$('.tab').forEach(item => item.classList.toggle('active', item === tab));
  $$('.tab-panel').forEach(item => item.classList.toggle('active', item === panel));
  if (name === 'graph') drawGraph();
  else if (name === 'report') renderReport();
  else $('#graphContainer').innerHTML = '';
}

                                              
const REPORT_TIER_META = {
  verified: {
    labelKey:'stats.veryHigh', rangeKey:'report.thresholdVerified', icon:'shield-check',
    descriptionKey:'report.verifiedHelp',
  },
  high_probability: {
    labelKey:'stats.highShort', rangeKey:'report.thresholdHigh', icon:'signal-high',
    descriptionKey:'report.highHelp',
  },
  medium_probability: {
    labelKey:'stats.mediumShort', rangeKey:'report.thresholdMedium', icon:'signal-medium',
    descriptionKey:'report.mediumHelp',
  },
  low_probability: {
    labelKey:'stats.lowShort', rangeKey:'report.thresholdLow', icon:'signal-low',
    descriptionKey:'report.lowHelp',
  },
  noise: {
    labelKey:'tier.noise', rangeKey:'report.thresholdNoise', icon:'signal-none',
    descriptionKey:'report.noiseHelp',
  },
  unknown: {
    labelKey:'tier.unknown', rangeKey:'common.noValidScore', icon:'info',
    descriptionKey:'detail.signalUnknownText',
  },
};

function reportTierMeta(tier) {
  const raw = REPORT_TIER_META[tier] || REPORT_TIER_META.unknown;
  return {
    ...raw,
    label:i18nT(raw.labelKey, {}, 'Unknown'),
    range:i18nT(raw.rangeKey, {}, 'No valid model score'),
    description:i18nT(raw.descriptionKey, {}, 'No valid model score was produced.'),
  };
}

const REPORT_SIGNAL_COPY = {
  'connection-cluster': {
    title:'Hedef çevresinde',
    text:'Hedefin çevresindeki hesap önerilerinde görüldü.',
  },
  'stable-surface': {
    title:'Tekrarlı eşleşme',
    text:'Birden fazla analiz alanında tekrar görüldü.',
  },
  'repeated-discovery': {
    title:'Ağ taraması',
    text:'Tekrarlanan ağ taramalarında görünür oldu.',
  },
  'general-suggestion': {
    title:'Genel öneri',
    text:'Instagram genel önerilerinde görüldü.',
  },
  'instagram-suggestion': {
    title:'Öneri eşleşmesi',
    text:'Giriş yapılan oturumun kişi önerilerinde görüldü.',
  },
  'reciprocal-chain': {
    title:'Karşılıklı öneri örtüşmesi',
    text:'Hedef çevresindeki öneri zincirinde iki yönlü eşleşme görüldü; bu takip kanıtı değildir.',
  },
  likes: {
    title:'Beğeni işareti',
    text:'İçeriklerde beğeni etkileşimi bulundu.',
  },
  comments: {
    title:'Yorum işareti',
    text:'İçeriklerde yorum etkileşimi bulundu.',
  },
  tags: {
    title:'Etiket işareti',
    text:'Etiket üzerinden bir bağlantı işareti bulundu.',
  },
  'co-tags': {
    title:'Ortak etiket',
    text:'Aynı içerikte birlikte etiketlenme işareti bulundu.',
  },
  'share-ranking': {
    title:'Paylaşım önerisi',
    text:'Giriş yapılan oturumun paylaşım önerilerinde görüldü.',
  },
  'mutual-followers': {
    title:'Ortak hesaplar',
    text:'Ortak takipçi bilgisi bulundu.',
  },
  'other-signal': {
    title:'Destekleyici eşleşme',
    text:'Analiz sırasında ek bir eşleşme bulundu.',
  },
};

function reportGeneratedDate(value) {
  if (value == null || value === '') return '';
  const numeric = Number(value);
  const date = Number.isFinite(numeric)
    ? new Date(numeric < 1e12 ? numeric * 1000 : numeric)
    : new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  if (appI18n && typeof appI18n.formatDate === 'function') {
    return appI18n.formatDate(date, {dateStyle:'medium', timeStyle:'short'});
  }
  return new Intl.DateTimeFormat('en-US', {dateStyle:'medium', timeStyle:'short'}).format(date);
}

function reportPersonSignals(person) {
  const viewerRelative = new Set([
    'following-signal', 'followed-signal', 'notifications',
    'mutual-followers',
    'friendship-following', 'friendship-followed-by',
    'friendship-outgoing-request', 'friendship-incoming-request',
    'friendship-bestie', 'friendship-favorite', 'friendship-muted',
    'friendship-limited',
  ]);
  return detailSignals(person)
    .filter(signal => signal && !viewerRelative.has(signal.key))
    .map(signal => ({
      ...signal,
      ...(REPORT_SIGNAL_COPY[signal.key] || REPORT_SIGNAL_COPY['other-signal']),
    }))
    .map(signal => ({...signal, title:i18nText(signal.title), text:i18nText(signal.text)}));
}

function reportTargetFacts(data) {
  const intel = data.target_intel || {};
  const identity = intel.identity || {};
  const profile = intel.profile || {};
  const privacy = intel.privacy || {};
  const counts = intel.leaked_counts || {};
  const crossPlatform = intel.cross_platform || {};
  const threads = crossPlatform.threads_user || {};
  const highlights = intel.story_highlights || {};
  const avatar = intel.avatar || {};
  const geo = ((intel.geo_inference || {}).final_inference) || {};
  const visibility = targetIntelFirst(privacy.is_private, profile.is_private, identity.is_private);
  const blueTick = targetIntelFirst(privacy.is_verified, profile.is_verified, identity.is_verified);
  const accountType = targetIntelAccountType({
    account_type:targetIntelFirst(identity.account_type, profile.account_type),
    is_business:targetIntelFirst(identity.is_business, profile.is_business),
    is_professional_account:targetIntelFirst(identity.is_professional_account, profile.is_professional_account),
  });
  const followers = targetIntelFirst(
    profile.follower_count, profile.og_follower_count,
    counts.follower_count, counts.gql_followers_total,
  );
  const following = targetIntelFirst(
    profile.following_count, profile.og_following_count, counts.following_count,
  );
  const posts = targetIntelFirst(profile.media_count, profile.og_media_count, counts.media_count);
  const threadsFollowers = targetIntelFirst(
    threads.follower_count, crossPlatform.threads_followers_count, counts.threads_follower_count,
  );
  const facts = [
    accountType ? {icon:'user', label:'Hesap türü', value:accountType} : null,
    typeof visibility === 'boolean' ? {
      icon:visibility ? 'lock' : 'eye', label:'Profil görünürlüğü',
      value:visibility ? 'Gizli profil' : 'Herkese açık',
    } : null,
    typeof blueTick === 'boolean' ? {
      icon:blueTick ? 'check' : 'circle', label:'Instagram mavi tiki',
      value:blueTick ? 'Var' : 'Yok',
    } : null,
    followers != null ? {icon:'users', label:'Instagram takipçisi', value:targetIntelCount(followers)} : null,
    following != null ? {icon:'arrow-right', label:'Takip ettiği', value:targetIntelCount(following)} : null,
    posts != null ? {icon:'grid', label:'Gönderi', value:targetIntelCount(posts)} : null,
    threadsFollowers != null ? {icon:'globe', label:'Threads takipçisi', value:targetIntelCount(threadsFollowers)} : null,
    highlights.highlight_count != null ? {
      icon:'image', label:'Öne çıkan hikâye', value:targetIntelCount(highlights.highlight_count),
    } : null,
    avatar.avatar_uploaded_iso ? {
      icon:'clock', label:'Profil fotoğrafı güncellendi',
      value:targetIntelDate(avatar.avatar_uploaded_iso, true),
    } : null,
    geo.best_country_guess && ['high','medium'].includes(String(geo.confidence || '').toLowerCase()) ? {
      icon:'map-pin', label:'Yaklaşık ağ bölgesi',
      value:targetIntelCountry(geo.best_country_guess),
      note:'Dil ve ağ işaretlerinden tahmin; gerçek konum kanıtı değildir.',
    } : null,
  ].filter(Boolean);
  return {
    identity, profile, privacy, accountType, visibility, blueTick, facts,
    biography:identity.biography || profile.biography || threads.biography || '',
  };
}

function reportSignalSummary(people) {
  const totals = new Map();
  for (const person of people) {
    for (const signal of reportPersonSignals(person)) {
      const current = totals.get(signal.key);
      if (current) current.people += 1;
      else totals.set(signal.key, {...signal, people:1});
    }
  }
  return Array.from(totals.values())
    .sort((a, b) => b.people - a.people || compareUiText(a.title, b.title))
    .slice(0, 8);
}

function renderReportGraphSnapshot(ownerUsername, totalPeople) {
  const frame = $('#reportGraphSnapshot');
  const graphContainer = $('#graphContainer');
  const minInput = $('#graphMinScore');
  if (!frame || !graphContainer || !minInput || !state.data) return;
  frame.style.removeProperty('aspect-ratio');
  const expectedOwner = String(ownerUsername || '');
  const previousMin = minInput.value;
  try {
                                                                                      
    minInput.value = '0';
    drawGraph();
    if (!state.data || String(state.data.username || state.username || '') !== expectedOwner) return;
    const source = graphContainer.querySelector('svg');
    if (!source) throw new Error('graph unavailable');
    const clone = source.cloneNode(true);
    clone.classList.add('report-network-svg');
    clone.setAttribute('role', 'img');
    clone.setAttribute('aria-label', i18nT('report.graphAria', {
      count:totalPeople,
    }, `Network view showing ${totalPeople} scored model candidates`));
    clone.setAttribute('preserveAspectRatio', 'xMidYMid meet');

    const idPrefix = `report-${state.loadRequestId}-`;
    const idMap = new Map();
    clone.querySelectorAll('[id]').forEach((element, index) => {
      const oldId = element.id;
      const nextId = `${idPrefix}${index}-${oldId}`;
      idMap.set(oldId, nextId);
      element.id = nextId;
    });
    clone.querySelectorAll('*').forEach(element => {
      element.removeAttribute('tabindex');
      if (element !== clone) element.removeAttribute('role');
      for (const attribute of Array.from(element.attributes || [])) {
        let value = attribute.value;
        for (const [oldId, nextId] of idMap) {
          value = value.split(`url(#${oldId})`).join(`url(#${nextId})`);
          if (value === `#${oldId}`) value = `#${nextId}`;
        }
        if (value !== attribute.value) element.setAttribute(attribute.name, value);
      }
    });
    clone.querySelectorAll('.is-selected').forEach(element => element.classList.remove('is-selected'));
    const pointForNode = node => {
      const match = String(node.getAttribute('transform') || '')
        .match(/translate\(\s*(-?[\d.]+)[, ]+\s*(-?[\d.]+)\s*\)/);
      return match ? {x:Number(match[1]), y:Number(match[2])} : null;
    };
    const allNodes = Array.from(clone.querySelectorAll('.graph-nodes .node'));
    const nodePoints = allNodes.map(pointForNode).filter(Boolean);
    if (nodePoints.length) {
      const minX = Math.min(...nodePoints.map(point => point.x)) - 70;
      const maxX = Math.max(...nodePoints.map(point => point.x)) + 70;
      const minY = Math.min(...nodePoints.map(point => point.y)) - 55;
      const maxY = Math.max(...nodePoints.map(point => point.y)) + 70;
      const cropWidth = maxX - minX;
      const cropHeight = maxY - minY;
      clone.setAttribute('viewBox', `${minX} ${minY} ${cropWidth} ${cropHeight}`);
      frame.style.aspectRatio = `${cropWidth} / ${cropHeight}`;
    }

                                                                                 
                                                                                
    const targetNode = clone.querySelector('.graph-nodes .node.target');
    const targetPoint = targetNode ? pointForNode(targetNode) : null;
    const chosen = [];
    for (const node of clone.querySelectorAll('.graph-nodes .node:not(.target)')) {
      const point = pointForNode(node);
      if (!point) continue;
      const targetDistance = targetPoint
        ? Math.hypot(point.x - targetPoint.x, point.y - targetPoint.y)
        : Infinity;
      if (targetDistance < 120) continue;
      if (chosen.some(previous => Math.hypot(point.x - previous.x, point.y - previous.y) < 92)) continue;
      node.classList.add('report-label-visible');
      chosen.push(point);
      if (chosen.length >= 9) break;
    }
    frame.replaceChildren(clone);
    translateUi(frame);
  } catch (_) {
    frame.innerHTML = '<div class="report-graph-empty"><b>Ağ görüntüsü hazırlanamadı</b><span>Network graph sekmesinden yeniden çizmeyi deneyin.</span></div>';
    translateUi(frame);
  } finally {
    minInput.value = previousMin;
    graphContainer.innerHTML = '';
    graphContainer.classList.remove('has-selection');
    state.graphController = null;
  }
}

function renderReport() {
  const root = $('#reportContent');
  const data = state.data;
  if (!root) return;
  if (!data) {
    root.innerHTML = '<div class="report-empty"><b>Henüz rapor yok</b><span>Önce bir kullanıcıyı sorgulayın.</span></div>';
    translateUi(root);
    return;
  }

  const owner = String(data.username || state.username || '');
  const target = targetDashboardPerson();
  const targetFacts = reportTargetFacts(data);
  const counts = dashboardTierCounts();
  const people = (data.people || []).slice().sort((a, b) =>
    (modelScore(b) ?? -1) - (modelScore(a) ?? -1)
    || Number(a.tier_rank || 0) - Number(b.tier_rank || 0)
    || compareUiText(String(a.username || a.pk || ''), String(b.username || b.pk || '')));
  const scoredPeopleCount = people.filter(hasValidModelScore).length;
  const generatedAt = reportGeneratedDate((data.meta || {}).generated_at);
  const tierCards = [
    {key:'total', label:'Yakalanan kişi', value:people.length, range:'Tam sonuç listesi', icon:'users'},
    ...['verified','high_probability','medium_probability','low_probability','noise'].map(key => ({
      key, label:key === 'noise'
        ? i18nT('stats.noise', {}, 'Insufficient / unknown')
        : reportTierMeta(key).label,
      value:counts[key],
      range:reportTierMeta(key).range, icon:REPORT_TIER_META[key].icon,
    })),
  ];
  const heroChips = [];
  if (targetFacts.accountType) heroChips.push(`<span>${escapeHtml(targetFacts.accountType)}</span>`);
  if (typeof targetFacts.visibility === 'boolean') {
    heroChips.push(`<span>${targetFacts.visibility ? 'Gizli profil' : 'Herkese açık profil'}</span>`);
  }
  if (targetFacts.blueTick === true) heroChips.push(`<span class="is-blue-tick">${uiIcon('check')} Instagram mavi tiki</span>`);

  const statHtml = tierCards.map(card => `<article class="report-stat t-${escapeAttr(card.key)}">
    <span class="report-stat-icon" aria-hidden="true">${uiIcon(card.icon)}</span>
    <div><small>${escapeHtml(card.label)}</small><strong>${escapeHtml(targetIntelCount(card.value))}</strong><span>${escapeHtml(card.range)}</span></div>
  </article>`).join('');

  const targetFactHtml = targetFacts.facts.length
    ? targetFacts.facts.map(fact => `<article class="report-target-fact">
        <span class="report-fact-icon" aria-hidden="true">${uiIcon(fact.icon)}</span>
        <div><small>${escapeHtml(fact.label)}</small><strong>${escapeHtml(fact.value)}</strong>${fact.note ? `<p>${escapeHtml(fact.note)}</p>` : ''}</div>
      </article>`).join('')
    : '<div class="report-inline-empty">Bu analizde temel profil bilgisi sınırlı.</div>';

  const signalSummary = reportSignalSummary(people);
  const signalSummaryHtml = signalSummary.length
    ? signalSummary.map(signal => `<article class="report-signal-card">
        <span aria-hidden="true">${uiIcon(signal.icon || 'info')}</span>
        <div><b>${escapeHtml(targetIntelCount(signal.people))} kişi</b><strong>${escapeHtml(signal.title)}</strong><p>${escapeHtml(signal.text)}</p></div>
      </article>`).join('')
    : '<div class="report-inline-empty">Bu sonuçlarda açıklanabilir ek sinyal bulunamadı.</div>';

  const personRows = people.map((person, index) => {
    const tier = canonicalTier(person);
    const tierMeta = reportTierMeta(tier);
    const score = modelScore(person);
    const signals = reportPersonSignals(person).slice(0, 3);
    const profileMeta = [];
    if (typeof person.is_private === 'boolean') {
      profileMeta.push(i18nT(person.is_private ? 'common.privateProfile' : 'common.publicProfile', {}, person.is_private ? 'Private profile' : 'Public profile'));
    }
    if (person.is_verified === true) profileMeta.push(i18nT('filter.blueTick', {}, 'Verified account'));
    const signalHtml = signals.length
      ? signals.map(signal => `<span title="${escapeAttr(signal.text)}"><i aria-hidden="true">${uiIcon(signal.icon || 'info')}</i>${escapeHtml(signal.title)}</span>`).join('')
      : `<span class="is-empty"><i aria-hidden="true">${uiIcon('circle')}</i>Ek sinyal yok</span>`;
    const personLabel = `@${person.username || person.pk || '?'}`;
    const personAria = i18nT('people.openPersonAria', {username:personLabel}, `Open details for ${personLabel}`);
    return `<button type="button" class="report-person-row t-${escapeAttr(tier)}" data-report-person-pk="${escapeAttr(person.pk)}" aria-label="${escapeAttr(personAria)}">
      <span class="report-person-index">${index + 1}</span>
      <span class="report-person-identity">
        ${profileAvatar(person, 'report-person-avatar')}
        <span><strong class="no-i18n">@${escapeHtml(person.username || person.pk || '?')}</strong><small class="${person.full_name ? 'no-i18n' : ''}">${escapeHtml(person.full_name || profileMeta.join(' · ') || 'İsim bilgisi yok')}</small>${person.full_name && profileMeta.length ? `<em>${escapeHtml(profileMeta.join(' · '))}</em>` : ''}</span>
      </span>
      <span class="report-person-probability">
        <span><b>${escapeHtml(formatModelScore(person))}</b><small>${escapeHtml(score == null ? i18nT('common.noValidScore', {}, 'No valid model score') : i18nT('common.modelConfidenceScore', {}, 'model-confidence score'))}</small></span>
        <i><u style="width:${score == null ? 0 : score}%"></u></i>
      </span>
      <span class="report-person-level"><b>${escapeHtml(tierMeta.label)}</b><small>${escapeHtml(tierMeta.range)}</small></span>
      <span class="report-person-signals">${signalHtml}</span>
      <span class="report-person-arrow" aria-hidden="true">${uiIcon('chevron-right')}</span>
    </button>`;
  }).join('');

  const instagramUrl = `https://www.instagram.com/${encodeURIComponent(owner)}/`;
  const threadsUrl = `https://www.threads.net/@${encodeURIComponent(owner)}`;
  root.innerHTML = `<div class="report-dashboard" data-report-owner="${escapeAttr(owner)}">
    <header class="report-card report-hero">
      <div class="report-hero-avatar">${profileAvatar(target, 'report-target-avatar')}</div>
      <div class="report-hero-copy">
        <span class="report-eyebrow">İlişki analizi raporu</span>
        <h1 class="no-i18n">@${escapeHtml(owner || '?')}</h1>
        ${target.full_name ? `<strong class="no-i18n">${escapeHtml(target.full_name)}</strong>` : ''}
        ${heroChips.length ? `<div class="report-chips">${heroChips.join('')}</div>` : ''}
        ${targetFacts.biography ? `<p class="no-i18n">${escapeHtml(targetFacts.biography)}</p>` : ''}
      </div>
      <div class="report-hero-side">
        ${generatedAt ? `<span>Son analiz<br><b>${escapeHtml(generatedAt)}</b></span>` : ''}
        <div><a href="${escapeAttr(instagramUrl)}" target="_blank" rel="noopener">Instagram ${uiIcon('external-link')}</a><a href="${escapeAttr(threadsUrl)}" target="_blank" rel="noopener">Threads ${uiIcon('external-link')}</a></div>
      </div>
      <div class="report-caveat"><span aria-hidden="true">${uiIcon('info')}</span><p><b>Skorlar model tahminidir.</b> Arkadaşlık, takip veya gerçek hayattaki yakınlığı tek başına kanıtlamaz.</p></div>
    </header>

    <section class="report-stat-grid" aria-label="Model güveni özeti">${statHtml}</section>

    <section class="report-main-grid">
      <figure class="report-card report-network-card">
        <header class="report-section-head">
          <div><span class="report-eyebrow">Ağ görüntüsü</span><h2>${escapeHtml(targetIntelCount(scoredPeopleCount))} skorlu aday haritada</h2></div>
          <span class="report-live-chip"><i></i> Skorlu model adayları</span>
        </header>
        <div id="reportGraphSnapshot" class="report-graph-frame"><div class="report-graph-loading">Ağ görüntüsü hazırlanıyor…</div></div>
        <div class="report-graph-legend">
          ${['verified','high_probability','medium_probability','low_probability','noise'].map(key => `<span class="t-${key}"><i></i>${escapeHtml(reportTierMeta(key).label)}</span>`).join('')}
        </div>
        <figcaption>Hedef merkezde; daha yüksek model skorları merkeze daha yakındır. Çizgiler öneri sinyallerinden hesaplanan aday bağlantılardır ve takip ilişkisini doğrulamaz.</figcaption>
      </figure>

      <aside class="report-card report-target-summary">
        <header class="report-section-head"><div><span class="report-eyebrow">Sorgulanan kişi</span><h2>Profil özeti</h2></div></header>
        <div class="report-target-facts">${targetFactHtml}</div>
        <p class="report-source-note">Yalnızca son analizde gerçekten alınabilen bilgiler gösterilir. Boş alanlardan sonuç çıkarılmaz.</p>
      </aside>
    </section>

    <section class="report-card report-signal-summary">
      <header class="report-section-head">
        <div><span class="report-eyebrow">Bağlantıyı etkileyen işaretler</span><h2>En sık görülen sinyaller</h2></div>
        <p>Rakam, bu işaretin kaç farklı kişide bulunduğunu gösterir.</p>
      </header>
      <div class="report-signal-grid">${signalSummaryHtml}</div>
    </section>

    <section class="report-card report-people-card">
      <header class="report-section-head">
        <div><span class="report-eyebrow">Yakalanan bilgiler</span><h2>Kişiler ve model güveni</h2></div>
        <div class="report-list-count"><b>${escapeHtml(targetIntelCount(people.length))}</b><span>kişi</span></div>
      </header>
      <div class="report-people-guide"><span>Kişi</span><span>Model skoru</span><span>Güven düzeyi</span><span>Bulunan işaretler</span></div>
      <div class="report-people-list">${personRows || '<div class="report-inline-empty">Bu analizde kişi bulunamadı.</div>'}</div>
      <p class="report-list-note">Bir kişinin ayrıntılarını ve kısa sinyal açıklamalarını görmek için satıra tıklayın. Aynı skoru alan kişiler arasında kesin bir sıralama yoktur.</p>
    </section>

    <section class="report-card report-method-card">
      <div><span aria-hidden="true">${uiIcon('percent')}</span><p><b>Model skoru</b> Sinyal ağırlıklarından üretilen, kalibre edilmemiş 0–100 güven skorudur; olasılık yüzdesi değildir.</p></div>
      <div><span aria-hidden="true">${uiIcon('network')}</span><p><b>Sinyal</b> Öneri, tekrar görünme veya etkileşim gibi tahmini destekleyen işaret.</p></div>
      <div><span aria-hidden="true">${uiIcon('alert-triangle')}</span><p><b>Sınır</b> Görünmeyen veya toplanmayan bilgi, “bağlantı yok” anlamına gelmez.</p></div>
    </section>

    <details class="report-raw-details">
      <summary>Teknik metin raporunu göster <span>Gelişmiş görünüm</span></summary>
      <pre>${escapeHtml(state.text || i18nT('report.rawUnavailable', {}, 'Technical text report is unavailable.'))}</pre>
    </details>
  </div>`;

  root.querySelectorAll('[data-report-person-pk]').forEach(row => {
    row.addEventListener('click', () => selectPerson(row.dataset.reportPersonPk, {openDetail:true}));
  });
  translateUi(root);
  renderReportGraphSnapshot(owner, scoredPeopleCount);
}

                                    
function bind() {
  $('#userSelect').addEventListener('change', e => loadUser(e.target.value));
  $('#runBtn').addEventListener('click', runEngine);
  $('#reloadBtn').addEventListener('click', () => state.username && loadUser(state.username));
  $('#searchBox').addEventListener('input', e => {
    state.search = e.target.value; applyFilters();
  });
  $('#minScore').addEventListener('input', e => {
    state.minScore = +e.target.value || 0; applyFilters();
  });
  $$('.chk-tier input').forEach(el => {
    el.addEventListener('change', () => {
      state.tiers[el.dataset.tier] = el.checked ? 1 : 0;
      applyFilters();
    });
  });
  $('#flagPriv').addEventListener('change', e => {
    state.flags.priv = e.target.checked ? 1 : 0; applyFilters(); });
  $('#flagVer').addEventListener('change', e => {
    state.flags.ver = e.target.checked ? 1 : 0; applyFilters(); });

               
  $$('#peopleTable thead th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
      const k = th.dataset.sort;
      if (state.sortKey === k) {
        state.sortDir = state.sortDir === 'desc' ? 'asc' : 'desc';
      } else {
        state.sortKey = k;
        state.sortDir = 'desc';
      }
      applyFilters();
    });
  });

         
  $$('.tab').forEach(t => {
    t.addEventListener('click', () => activateTab(t.dataset.tab));
  });

  $('#detailClose').addEventListener('click', closeDetail);
  $('#graphRedraw').addEventListener('click', drawGraph);
  $('#graphMinScore').addEventListener('change', event => {
    const next = Math.max(0, Math.min(100, Number(event.target.value) || 0));
    event.target.value = String(next);
    const mobile = $('#graphMinScoreMobile');
    if (mobile) mobile.value = String(next);
    renderPeopleRail();
    drawGraph();
  });
  const mobileGraphMin = $('#graphMinScoreMobile');
  if (mobileGraphMin) {
    mobileGraphMin.addEventListener('change', event => {
      const next = Math.max(0, Math.min(100, Number(event.target.value) || 0));
      event.target.value = String(next);
      $('#graphMinScore').value = String(next);
      renderPeopleRail();
      drawGraph();
    });
  }
  $('#graphZoomOut').addEventListener('click', () => state.graphController && state.graphController.zoomBy(1.22));
  $('#graphZoomIn').addEventListener('click', () => state.graphController && state.graphController.zoomBy(.82));
  $('#graphFit').addEventListener('click', () => state.graphController && state.graphController.fit());
  $('#targetReportBtn').addEventListener('click', () => activateTab('report'));
  $('#peopleRailAll').addEventListener('click', () => activateTab('people'));

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeDetail();
  });
}

                                                                             
                      
                                                                             

function renderTargetIntel() {
  const ti = state.data && state.data.target_intel;
  const c = $('#targetIntel');
  if (!ti || !Object.keys(ti).length) {
    c.innerHTML = '<p class="muted">target_intel bos. Engine\'i tekrar kos.</p>';
    return;
  }

  const cards = [];

                                             
  const id = ti.identity || {};
  const av = ti.avatar || {};
  const prof = ti.profile || {};
  const username = state.data.username;
  const fullName = id.full_name || prof.full_name || '';
  const targetIntelAvatarUrl = av.profile_pic_url || prof.profile_pic_url || '';
  const targetAvatarProxy = targetIntelAvatarUrl
    ? avatarProxyUrl({pk:id.pk || state.data.target_pk, profile_pic_url:targetIntelAvatarUrl})
    : '';
  cards.push(`
    <div class="t-card target-avatar wide">
      ${targetAvatarProxy ?
        `<img src="${escapeAttr(targetAvatarProxy)}" alt="" referrerpolicy="no-referrer" data-avatar-error="hide">` :
        '<div style="width:88px;height:88px;border:2px solid var(--line);border-radius:50%;background:var(--bg3)"></div>'}
      <div class="info">
        <div class="name">@${escapeHtml(username)} ${fullName? '· '+escapeHtml(fullName):''}</div>
        <div class="meta">pk=${escapeHtml(id.pk||'?')} · account_type=${id.account_type != null ? id.account_type : '?'} · is_business=${typeof id.is_business === 'boolean' ? String(id.is_business) : '?'}</div>
        ${prof.thread_context_items && prof.thread_context_items.length
          ? '<div class="t-followers-line">' +
            prof.thread_context_items.map(x => `<span><span class="num">${escapeHtml((x.text||'').split('·')[0].trim())}</span> ${escapeHtml((x.text||'').includes('·')?(x.text.split('·').slice(1).join('·')):' ')}</span>`).join('') +
            '</div>'
          : ''}
        <div class="links">
          <a href="https://www.instagram.com/${encodeURIComponent(username)}/" target="_blank" rel="noopener">Instagram</a>
          <a href="https://www.threads.net/@${encodeURIComponent(username)}" target="_blank" rel="noopener">Threads</a>
        </div>
      </div>
    </div>`);

                                  
  const ac = ti.account_creation || {};
  if (Object.keys(ac).length) {
    cards.push(`<div class="t-card">
      <h3>katilma & DSA transparency</h3>
      ${kvList(ac, [
        ['date_joined_iso', 'Hesap acilis (UTC)'],
        ['date_joined_unix', 'unix ts'],
        ['account_creation_country', 'olusturma ulkesi'],
        ['account_creation_country_text', 'ulke (text)'],
        ['account_creation_year_month', 'olusturma yil/ay'],
        ['joined_year_month_text', 'yil/ay (text)'],
        ['account_age_month', 'hesap yasi (ay)'],
        ['former_usernames', 'eski kullanici adlari'],
        ['name_changes_count', 'isim degisiklik sayisi'],
        ['account_takeover_count', 'el degistirme sayisi'],
        ['shared_followers_count', 'ortak takipci'],
        ['has_run_ads', 'reklam vermis mi'],
        ['has_run_political_ads', 'siyasi reklam'],
      ])}
    </div>`);
  }

                          
  const dm = ti.dm_state || {};
  if (Object.keys(dm).filter(k => dm[k] != null).length) {
    cards.push(`<div class="t-card">
      <h3>DM state (mesajlasma)</h3>
      ${kvList(dm, [
        ['reachability_status_meaning', 'mesaj erisilebilirlik'],
        ['reachability_status_code', 'kod'],
        ['is_viewer_unconnected', 'viewer takipsiz'],
        ['responsiveness_category', 'yanit kategori'],
        ['should_show_safety_card', 'guvenlik karti'],
        ['has_reached_message_request_limit', 'request limit dolu'],
        ['is_appointment_booking_enabled', 'randevu mesaji'],
      ])}
      ${dm.live_presence ? `<div style="margin-top:.6em;padding-top:.5em;border-top:1px solid var(--line)">
        <strong style="color:var(--accent);font-size:.85em">canli presence:</strong>
        ${kvList(dm.live_presence, [
          ['is_active', 'aktif'],
          ['in_threads', 'DM\'de'],
          ['last_activity_iso', 'son aktivite'],
          ['seconds_since_active', 'saniye once'],
          ['source', 'endpoint'],
        ])}
      </div>` : ''}
      ${dm.existing_dm_thread ? `<div style="margin-top:.6em;padding-top:.5em;border-top:1px solid var(--line)">
        <strong style="color:var(--accent);font-size:.85em">mevcut DM thread:</strong>
        ${kvList(dm.existing_dm_thread, [
          ['inbox', 'inbox tipi'],
          ['thread_id', 'thread_id'],
          ['thread_v2_id', 'thread_v2_id'],
          ['last_permanent_item_iso', 'son mesaj'],
          ['last_activity_iso', 'son aktivite'],
          ['last_item_user_pk', 'son mesaji yazan'],
          ['last_item_type', 'mesaj tipi'],
          ['last_item_text_head', 'son mesaj baslik'],
          ['inviter_pk', 'davet eden'],
          ['muted', 'sessiz'],
          ['marked_as_unread', 'okunmamis'],
        ])}
      </div>` : ''}
    </div>`);
  }

                                              
  const fr = ti.friendship || {};
  if (Object.keys(fr).length) {
    cards.push(`<div class="t-card">
      <h3>friendship (viewer ↔ target)</h3>
      ${kvList(fr, Object.keys(fr).sort().map(k => [k, k]))}
    </div>`);
  }

                                  
  if (Object.keys(av).length) {
    cards.push(`<div class="t-card">
      <h3>avatar forensics</h3>
      ${kvList(av, [
        ['avatar_uploaded_iso', 'son avatar upload'],
        ['avatar_age_days', 'gun once'],
        ['uploader_pk', 'yukleyen pk'],
        ['uploader_matches_target', 'target mi yukledi'],
        ['stolen_avatar_signal', 'calinti sinyali'],
        ['media_id', 'media id'],
        ['hex', 'hex'],
      ])}
    </div>`);
  }

                         
  const pr = ti.privacy || {};
  const prFiltered = Object.fromEntries(Object.entries(pr).filter(([_,v])=>v!=null));
  if (Object.keys(prFiltered).length) {
    cards.push(`<div class="t-card">
      <h3>privacy & flags</h3>
      ${kvList(prFiltered, Object.keys(prFiltered).map(k => [k, k]))}
    </div>`);
  }

                                    
  const profDisplay = {};
  ['biography','category_name','category','is_business','is_professional_account',
   'follower_count','following_count','media_count',
   'og_follower_count','og_following_count','og_media_count',
   'public_email','public_phone_number','public_phone_country_code',
   'business_email','business_phone_number','business_contact_method',
   'external_url','external_lynx_url','connected_fb_page',
   'biography_email_addresses','biography_phone_numbers',
   'bio_emails_extracted','bio_phones_extracted',
   'category_id','address_street','city_name','zip','latitude','longitude'
  ].forEach(k => { if (prof[k] != null && prof[k] !== '') profDisplay[k] = prof[k]; });
  if (Object.keys(profDisplay).length) {
    cards.push(`<div class="t-card">
      <h3>profile / business</h3>
      ${kvList(profDisplay, Object.keys(profDisplay).map(k => [k, k]))}
    </div>`);
  }

                           
  const bl = ti.bio_links || [];
  if (bl.length) {
    cards.push(`<div class="t-card">
      <h3>bio links (${bl.length})</h3>
      ${bl.map((l,i) => `
        <div style="padding:.35em 0;border-bottom:1px solid #1c1f29;font-family:var(--mono);font-size:.85em">
          <div><strong>${escapeHtml(l.title || '(no title)')}</strong> <span class="muted">${escapeHtml(l.link_type||'')}</span></div>
          ${l.url ? `<a href="${escapeAttr(l.url)}" target="_blank" rel="noopener" style="font-size:.85em">${escapeHtml(l.url)}</a>` : ''}
        </div>`).join('')}
    </div>`);
  }

                                    
  const sh = ti.story_highlights || {};
  if (sh.highlight_count != null && sh.highlight_count > 0 ||
      (sh.timing_endpoints && sh.timing_endpoints.length)) {
    const timingHtml = (sh.timing_endpoints||[]).map(t => `
      <div style="padding:.25em 0;font-family:var(--mono);font-size:.8em">
        <strong>${escapeHtml(t.endpoint)}</strong>
        ${t.latest_reel_media_iso?` latest=${escapeHtml(t.latest_reel_media_iso)}`:''}
        ${t.expiring_at_iso?` expires=${escapeHtml(t.expiring_at_iso)}`:''}
        ${t.item_count?` items=${t.item_count}`:''}
        ${t.highlight_count?` highlights=${t.highlight_count}`:''}
      </div>`).join('');
    const hlHtml = (sh.highlights||[]).slice(0,15).map(h => `
      <div style="padding:.25em 0;font-family:var(--mono);font-size:.8em">
        <strong>${escapeHtml(h.title||'(untitled)')}</strong>
        media=${h.media_count||0}
        ${h.created_at_iso?` created=${escapeHtml((h.created_at_iso||'').slice(0,10))}`:''}
        ${h.latest_reel_media_iso?` latest=${escapeHtml((h.latest_reel_media_iso||'').slice(0,10))}`:''}
        ${h.is_pinned_highlight?' [pinned]':''}
      </div>`).join('');
    cards.push(`<div class="t-card">
      <h3>story / highlights</h3>
      <div class="kv"><dt>highlight_count</dt><dd>${sh.highlight_count||0}</dd></div>
      ${hlHtml || (timingHtml ? '' : '<p class="t-empty">aktif story / highlight yok</p>')}
      ${timingHtml ? `<div style="margin-top:.6em;padding-top:.5em;border-top:1px solid var(--line)">
        <strong style="color:var(--accent);font-size:.85em">story timing endpoints:</strong>
        ${timingHtml}
      </div>` : ''}
    </div>`);
  }

                                  
  const bo = ti.birthday_oracle || {};
  if (Object.keys(bo).length && bo.value !== undefined) {
    cards.push(`<div class="t-card">
      <h3>birthday oracle</h3>
      ${kvList(bo, [
        ['value', 'visibility_for_viewer'],
        ['has_birthday_data', 'IG\'de DOB var'],
        ['birthday_is_today', 'bugun mu'],
        ['inference_note', 'not'],
      ])}
    </div>`);
  }

                                                        
  const geo = ti.geographic || {};
  if (geo.signals && geo.signals.length) {
    cards.push(`<div class="t-card">
      <h3>geographic raw signals (Phase 33)</h3>
      <ul style="margin:0;padding-left:1.2em;font-family:var(--mono);font-size:.8em">
        ${(geo.signals||[]).map(s => `<li>${escapeHtml(s)}</li>`).join('')}
      </ul>
      ${(geo.inferences||[]).length ? `
        <div style="margin-top:.5em;color:var(--accent2);font-family:var(--mono);font-size:.8em">
          <strong>raw inferences:</strong>
          <ul style="margin:.2em 0;padding-left:1.2em">
            ${geo.inferences.map(i => `<li>${escapeHtml(i)}</li>`).join('')}
          </ul>
        </div>` : ''}
    </div>`);
  }

                                                              
  const gi = ti.geo_inference || {};
  if (Object.keys(gi).length) {
    cards.push(renderGeoInference(gi));
  }

                           
  const mids = ti.meta_ids || {};
  if (Object.keys(mids).filter(k=>mids[k]).length) {
    cards.push(`<div class="t-card">
      <h3>Meta IDs (cross-platform)</h3>
      ${kvList(mids, [
        ['fbid_v2', 'fbid_v2 (IG-side)'],
        ['interop_messaging_user_fbid', 'Messenger interop ID'],
        ['eimu_id', 'eimu_id'],
        ['threads_url', 'Threads URL'],
        ['threads_profile_glyph_url', 'Threads glyph URL (xmt)'],
        ['fbid_v2_is_ig_format', 'IG format'],
        ['interop_id_note', 'not'],
      ])}
    </div>`);
  }

                                
  const fb = ti.fb_resolution || {};
  if (fb.fb_profile_candidates && fb.fb_profile_candidates.length) {
    cards.push(`<div class="t-card">
      <h3>FB profile candidates</h3>
      ${fb.fb_profile_candidates.map(c => `
        <div style="padding:.25em 0;font-family:var(--mono);font-size:.85em">
          <span class="muted">${escapeHtml(c.source)}</span>
          → <a href="${escapeAttr(c.url)}" target="_blank" rel="noopener">${escapeHtml(c.url)}</a>
        </div>`).join('')}
    </div>`);
  }

                                           
  const cp = ti.cross_platform || {};
  if (cp.threads_user || cp.threads_followers_count || cp.threads_post_count) {
    cards.push(`<div class="t-card">
      <h3>Threads profile</h3>
      ${cp.threads_user ? kvList(cp.threads_user, [
        ['username', 'username'], ['full_name', 'full_name'],
        ['follower_count', 'followers'], ['following_count', 'following'],
        ['media_count', 'posts'], ['is_private', 'private'],
        ['biography', 'bio'],
      ]) : ''}
      ${cp.threads_followers_count ? `<div class="kv"><dt>endpoint followers</dt><dd>${cp.threads_followers_count}</dd></div>` : ''}
      ${cp.threads_post_count ? `<div class="kv"><dt>endpoint posts</dt><dd>${cp.threads_post_count}</dd></div>` : ''}
    </div>`);
  }

                           
  const rec = ti.recovery || {};
  if (Object.keys(rec).length) {
    cards.push(`<div class="t-card">
      <h3>recovery (rate-limited?)</h3>
      ${kvList(rec, Object.keys(rec).map(k => [k, k]))}
    </div>`);
  }

                                
  const ex = ti.extras || {};
  if (Object.keys(ex).length) {
    cards.push(`<div class="t-card">
      <h3>UI-hidden extras</h3>
      ${kvList(ex, Object.keys(ex).map(k => [k, k]))}
    </div>`);
  }

                                   
  const bt = ti.behavior_toggles || {};
  if (Object.keys(bt).length) {
    cards.push(`<div class="t-card">
      <h3>🛡 behavior & privacy toggles</h3>
      ${kvList(bt, Object.keys(bt).map(k => [k, k]))}
    </div>`);
  }

                                       
  const pp = ti.personal_prefs || {};
  if (Object.keys(pp).length) {
    let html = `<h3>🎭 personal preferences</h3>`;
    if (pp.nametag) {
      const nt = pp.nametag;
      html += `<div style="display:flex;align-items:center;gap:.7em;margin-bottom:.6em">
        <div style="font-size:2em">${escapeHtml(nt.emoji||'?')}</div>
        <div style="font-family:var(--mono);font-size:.85em">
          <div>nametag emoji: <strong>${escapeHtml(nt.emoji||'(yok)')}</strong></div>
          <div class="muted">theme=${nt.selected_theme_color} mode=${nt.mode} gradient=${nt.gradient}</div>
        </div>
      </div>`;
    }
    if (pp.qa_banner_prompts && pp.qa_banner_prompts.length) {
      html += `<div style="margin-bottom:.5em">
        <div class="muted" style="font-size:.78em;margin-bottom:.25em">Q&A banner mevcut promptlar:</div>
        <div style="display:flex;flex-wrap:wrap;gap:.3em">
          ${pp.qa_banner_prompts.map(p => `<span class="evchip">${escapeHtml(p.display_text||p.prompt)}</span>`).join('')}
        </div>
      </div>`;
    }
    if (pp.qa_banner_transparency) {
      html += `<div class="muted" style="font-size:.78em;margin-bottom:.4em">${escapeHtml(pp.qa_banner_transparency)}</div>`;
    }
    if (pp.pronouns && pp.pronouns.length) {
      html += `<div class="kv"><dt>pronouns</dt><dd>${escapeHtml(pp.pronouns.join(', '))}</dd></div>`;
    }
    if (pp.account_badges && pp.account_badges.length) {
      html += `<div class="kv"><dt>account_badges</dt><dd>${escapeHtml(JSON.stringify(pp.account_badges))}</dd></div>`;
    }
    if (pp.avatar_status) {
      html += `<div class="kv"><dt>avatar_status</dt><dd>${escapeHtml(JSON.stringify(pp.avatar_status))}</dd></div>`;
    }
    cards.push(`<div class="t-card">${html}</div>`);
  }

                               
  const mo = ti.monetization || {};
  if (Object.keys(mo).length) {
    cards.push(`<div class="t-card">
      <h3>💰 monetization & subscription</h3>
      ${kvList(mo, Object.keys(mo).map(k => [k, k]))}
    </div>`);
  }

                                
  const lc = ti.leaked_counts || {};
  if (Object.keys(lc).length) {
    cards.push(`<div class="t-card">
      <h3>🔢 leaked numerical counts</h3>
      ${kvList(lc, [
        ['follower_count', 'follower (info)'],
        ['gql_followers_total', 'follower (GraphQL leak)'],
        ['following_count', 'following'],
        ['media_count', 'media'],
        ['usertags_count', 'usertags'],
        ['total_clips_count', 'clips'],
        ['mutual_followers_count', 'mutual followers'],
        ['threads_follower_count', 'Threads followers'],
        ['threads_following_count', 'Threads following'],
        ['threads_media_count', 'Threads posts'],
      ])}
    </div>`);
  }

                                                                     
  const fg = ti.friendship_grid || {};
  if (fg.rows && fg.rows.length) {
    const c = fg.counts || {};
    const rows = fg.rows.slice(0, 60);
    cards.push(`<div class="t-card wide">
      <h3>👥 friendship grid — viewer ↔ X (${fg.rows.length} cluster user)</h3>
      <div style="font-family:var(--mono);font-size:.78em;margin-bottom:.6em;color:var(--fg-mute)">
        following=${c.fs_following} · followed_by=${c.fs_followed_by}
        · bestie=${c.fs_is_bestie} · subscribed=${c.fs_subscribed}
        · feed_fav=${c.fs_is_feed_favorite} · blocking=${c.fs_blocking}
        · restricted=${c.fs_is_restricted} · req_in=${c.fs_incoming_request}
        · req_out=${c.fs_outgoing_request} · private=${c.is_private_count}
        · verified=${c.is_verified_count}
      </div>
      <div style="overflow-x:auto">
        <table style="width:100%;font-family:var(--mono);font-size:.72em;border-collapse:collapse">
          <thead>
            <tr style="background:var(--bg3)">
              <th style="text-align:left;padding:.3em;border-bottom:1px solid var(--line)">@user</th>
              <th title="X follows me" style="padding:.2em;border-bottom:1px solid var(--line)">→</th>
              <th title="I follow X" style="padding:.2em;border-bottom:1px solid var(--line)">←</th>
              <th title="bestie / close friend" style="padding:.2em;border-bottom:1px solid var(--line)">★</th>
              <th title="subscribed (paid)" style="padding:.2em;border-bottom:1px solid var(--line)">$</th>
              <th title="in 'Favorites' feed" style="padding:.2em;border-bottom:1px solid var(--line)">⭐</th>
              <th title="X requested to follow me" style="padding:.2em;border-bottom:1px solid var(--line)">RQin</th>
              <th title="I requested to follow X" style="padding:.2em;border-bottom:1px solid var(--line)">RQout</th>
              <th title="muting" style="padding:.2em;border-bottom:1px solid var(--line)">🔇</th>
              <th title="restricted" style="padding:.2em;border-bottom:1px solid var(--line)">⛔</th>
              <th title="blocking" style="padding:.2em;border-bottom:1px solid var(--line)">🚫</th>
              <th title="private" style="padding:.2em;border-bottom:1px solid var(--line)">P</th>
              <th title="verified" style="padding:.2em;border-bottom:1px solid var(--line)">V</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map(r => `
              <tr style="border-bottom:1px solid #1c1f29">
                <td style="padding:.3em"><a href="https://www.instagram.com/${encodeURIComponent(r.username||'')}/" target="_blank" rel="noopener">@${escapeHtml(r.username||'?')}</a></td>
                ${fgCell(r.fs_following)}
                ${fgCell(r.fs_followed_by)}
                ${fgCell(r.fs_is_bestie, '#6cf0a0')}
                ${fgCell(r.fs_subscribed, '#ffd166')}
                ${fgCell(r.fs_is_feed_favorite, '#ffd166')}
                ${fgCell(r.fs_incoming_request)}
                ${fgCell(r.fs_outgoing_request)}
                ${fgCell(r.fs_muting, '#ff8a8a')}
                ${fgCell(r.fs_is_restricted, '#ff8a8a')}
                ${fgCell(r.fs_blocking, '#ff5d8f')}
                ${fgCell(r.is_private)}
                ${fgCell(r.is_verified, '#ffd166')}
              </tr>`).join('')}
          </tbody>
        </table>
      </div>
      ${fg.rows.length > 60 ? `<div class="muted" style="margin-top:.4em">+${fg.rows.length-60} daha</div>` : ''}
    </div>`);
  }

                                  
  if (ti.cross_platform && ti.cross_platform.threads_user) {
    const tu = ti.cross_platform.threads_user;
    if (tu.is_private === false) {
                                               
      cards.push(`<div class="t-card" style="border-left:4px solid #ffd166">
        <h3>⚠ Threads PUBLIC (IG private!)</h3>
        <div class="muted" style="font-size:.85em;margin-bottom:.4em">
          Target IG'de gizli ama Threads'te public. Threads post atarsa görülür.
        </div>
        ${kvList(tu, [
          ['username', 'username'], ['full_name', 'full_name'],
          ['follower_count', 'followers'], ['following_count', 'following'],
          ['media_count', 'posts'], ['biography', 'bio'],
        ])}
      </div>`);
    }
  }

                                         
  if (Object.keys(ti.cdn_forensics||{}).length || Object.keys(ti.header_forensics||{}).length) {
    cards.push(`<div class="t-card">
      <h3>CDN & header forensics</h3>
      ${ti.cdn_forensics && ti.cdn_forensics.cdn_region_code ? `
        <div class="kv"><dt>CDN region</dt><dd>${escapeHtml(ti.cdn_forensics.cdn_region_hint||ti.cdn_forensics.cdn_region_code)} <span class="muted">(viewer-side)</span></dd></div>
        <div class="kv"><dt>CDN POP</dt><dd>${escapeHtml(ti.cdn_forensics.cdn_pop||'')}/${escapeHtml(ti.cdn_forensics.cdn_node||'')}</dd></div>
      ` : ''}
      ${ti.header_forensics && ti.header_forensics.target_context && Object.keys(ti.header_forensics.target_context).length ? `
        <strong style="color:var(--accent);font-size:.85em">target_context:</strong>
        ${kvList(ti.header_forensics.target_context, Object.keys(ti.header_forensics.target_context).map(k => [k, k]))}
      ` : ''}
    </div>`);
  }

  c.innerHTML = cards.join('');
}

function renderGeoInference(gi) {
  const fi = gi.final_inference || {};
  const tz = gi.timezone_inference || {};
  const ah = gi.avatar_upload_histogram || {};
  const bio = gi.bio_text_matches || {};
  const tl = gi.tagged_locations || {};
  const cd = gi.cluster_country_distribution || {};

  const confColor = {high:'#5cd6a8', medium:'#ffd166', low:'#ff8fc1', none:'#666'};
  const cc = confColor[fi.confidence] || '#777';

                           
  let html = `<div class="t-card wide" style="border-left:4px solid ${cc}">
    <h3>📍 GEOGRAPHIC INFERENCE (multi-signal fusion)</h3>`;

  if (fi.best_country_guess) {
    html += `
    <div style="display:flex;gap:1em;align-items:center;margin-bottom:.7em">
      <div>
        <div class="muted" style="font-size:.7em;text-transform:uppercase;letter-spacing:.07em">best guess</div>
        <div style="font-family:var(--mono);font-size:1.6em;font-weight:600;color:${cc}">
          ${escapeHtml(fi.best_country_guess)}
        </div>
      </div>
      <div>
        <div class="muted" style="font-size:.7em;text-transform:uppercase">score</div>
        <div style="font-family:var(--mono);font-size:1.4em">${fi.best_score}</div>
      </div>
      <div>
        <div class="muted" style="font-size:.7em;text-transform:uppercase">confidence</div>
        <div style="font-family:var(--mono);font-size:1.2em;color:${cc}">${escapeHtml(fi.confidence)}</div>
      </div>
    </div>`;
                 
    const cands = Object.entries(fi.all_candidates || {}).slice(0, 12);
    if (cands.length > 1) {
      const max = cands[0][1];
      html += `<div style="margin-top:.4em">
        <div class="muted" style="font-size:.75em;margin-bottom:.3em">tüm adaylar (sıralı):</div>
        ${cands.map(([c, s]) => `
          <div style="display:flex;align-items:center;gap:.5em;font-family:var(--mono);font-size:.8em;padding:.1em 0">
            <span style="min-width:10em">${escapeHtml(c)}</span>
            <div style="flex:1;background:#222;border-radius:3px;height:.6em;position:relative;overflow:hidden">
              <div style="position:absolute;left:0;top:0;bottom:0;width:${(s/max*100).toFixed(0)}%;background:${cc};opacity:.7"></div>
            </div>
            <span style="min-width:3em;text-align:right">${s.toFixed(2)}</span>
          </div>`).join('')}
      </div>`;
    }
  } else {
    html += `<p class="muted">Yeterli sinyal yok. Daha fazla phase çalıştır (presence, archeology, news, tagged).</p>`;
  }

              
  if (fi.reasoning && fi.reasoning.length) {
    html += `<div style="margin-top:.6em;padding-top:.5em;border-top:1px solid var(--line)">
      <div class="muted" style="font-size:.75em;margin-bottom:.3em">reasoning:</div>
      <ul style="margin:0;padding-left:1.2em;font-family:var(--mono);font-size:.78em;line-height:1.5">
        ${fi.reasoning.map(r => `<li>${escapeHtml(r)}</li>`).join('')}
      </ul>
    </div>`;
  }
  html += `</div>`;

                            
  if (tz.sample_count > 0 || tz.estimated_local_timezone) {
    html += `<div class="t-card">
      <h3>🕐 timezone inference (target activity)</h3>
      ${kvList(tz, [
        ['sample_count', 'sample sayısı'],
        ['estimated_local_timezone', 'tahmin edilen TZ'],
        ['low_activity_window_utc', 'uyku penceresi (UTC)'],
        ['high_activity_window_utc', 'aktif pencere (UTC)'],
      ])}
      ${tz.estimated_country_hints && tz.estimated_country_hints.length ?
        `<div class="muted" style="font-size:.85em;margin-top:.3em">→ ${tz.estimated_country_hints.join(', ')}</div>` : ''}
      ${renderHourBars(tz.hour_histogram_utc)}
      <div class="muted" style="font-size:.75em;margin-top:.4em">${escapeHtml(tz.note || '')}</div>
    </div>`;
  } else {
    html += `<div class="t-card">
      <h3>🕐 timezone inference</h3>
      <p class="t-empty">${escapeHtml(tz.note || 'target aktivite timestamp yok — Phase 26/29/31 gerekir')}</p>
    </div>`;
  }

                                      
  if (ah.decoded_count >= 20) {
    html += `<div class="t-card">
      <h3>👥 cluster avatar upload pattern</h3>
      <div class="kv">
        <dt>decoded</dt><dd>${ah.decoded_count} / ${ah.cluster_size}</dd>
        <dt>peak window UTC</dt><dd>${(ah.peak_window_utc||[]).join('-')}</dd>
      </div>
      ${renderHourBars(ah.hour_histogram_utc, ah.peak_window_utc)}
      <div class="muted" style="font-size:.75em;margin-top:.3em">cluster üyelerinin avatar yükleme saatleri (UTC). Ortak peak target ile aynı timezone halkasını gösterir.</div>
    </div>`;
  }

                     
  if (tl.distinct_count > 0) {
    html += `<div class="t-card">
      <h3>🗺 tagged location centroid</h3>
      <div class="kv">
        <dt>distinct locations</dt><dd>${tl.distinct_count}</dd>
        ${tl.centroid ? `
        <dt>centroid lat/lng</dt><dd>${tl.centroid.lat}, ${tl.centroid.lng} <a href="https://www.google.com/maps?q=${tl.centroid.lat},${tl.centroid.lng}" target="_blank" rel="noopener">[map]</a></dd>
        <dt>geo points</dt><dd>${tl.centroid.point_count}</dd>` : ''}
      </div>
      ${(tl.top_locations||[]).slice(0,8).map(l => `
        <div style="padding:.2em 0;font-family:var(--mono);font-size:.8em">
          📍 <strong>${escapeHtml(l.name||'?')}</strong>
          ${l.city ? `<span class="muted">${escapeHtml(l.city)}</span>` : ''}
          ${l.lat && l.lng ? `<a href="https://www.google.com/maps?q=${l.lat},${l.lng}" target="_blank" rel="noopener" class="muted">[${l.lat},${l.lng}]</a>` : ''}
          <span style="background:var(--bg3);padding:0 .35em;border-radius:3px;margin-left:.3em">x${l.count}</span>
        </div>`).join('')}
    </div>`;
  } else {
    html += `<div class="t-card">
      <h3>🗺 tagged locations</h3>
      <p class="t-empty">target tagged location yok (Phase 30 cluster_pivot bos)</p>
    </div>`;
  }

                
  if (bio.biography_present) {
    html += `<div class="t-card">
      <h3>📝 bio text scan</h3>
      ${bio.biography_head ? `<div style="background:var(--bg3);padding:.5em;border-radius:4px;font-family:var(--mono);font-size:.78em;margin-bottom:.5em">${escapeHtml(bio.biography_head)}</div>` : ''}
      ${bio.matches && bio.matches.length ? bio.matches.map(m => `
        <div style="padding:.2em 0;font-family:var(--mono);font-size:.8em">
          <span class="badge t-acquaintance">${escapeHtml(m.value)}</span>
          → <strong>${escapeHtml(m.country_hint||'?')}</strong>
          <span class="muted">(${m.pattern})</span>
        </div>`).join('') : '<p class="t-empty">bio metninde ülke/şehir yok</p>'}
    </div>`;
  }

                                 
  if (cd.is_in_eu_true_count > 0 || cd.is_in_canada_true_count > 0) {
    html += `<div class="t-card">
      <h3>🌍 cluster country flags</h3>
      ${kvList(cd, [
        ['sample_size', 'sample size'],
        ['is_in_eu_true_count', 'EU=true count'],
        ['is_in_eu_false_count', 'EU=false count'],
        ['is_in_canada_true_count', 'Canada=true count'],
      ])}
    </div>`;
  }

  return html;
}

function renderHourBars(hist, peak) {
  if (!hist) return '';
  const vals = Array.from({length:24}, (_, h) => +(hist[String(h)] || 0));
  const max = Math.max(1, ...vals);
  const peakSet = new Set();
  if (peak && peak.length === 2) {
    let [s, e] = peak;
    if (e >= s) {
      for (let i = s; i <= e; i++) peakSet.add(i);
    } else {
      for (let i = s; i < 24; i++) peakSet.add(i);
      for (let i = 0; i <= e; i++) peakSet.add(i);
    }
  }
  return `<div style="display:flex;align-items:flex-end;gap:1px;height:60px;margin:.5em 0 .2em;background:var(--bg3);padding:.3em;border-radius:4px">
    ${vals.map((v, h) => `
      <div title="UTC ${h}:00 = ${v}" style="flex:1;background:${peakSet.has(h)?'#ff5d8f':'var(--accent)'};height:${(v/max*100).toFixed(0)}%;min-height:2px;border-radius:1px"></div>`).join('')}
  </div>
  <div style="display:grid;grid-template-columns:repeat(24,1fr);font-family:var(--mono);font-size:.6em;color:var(--fg-mute);padding:0 .3em">
    ${Array.from({length:24}, (_,h) => `<span style="text-align:center">${h%3===0?h:''}</span>`).join('')}
  </div>`;
}

function fgCell(v, posColor) {
  if (v === true) {
    const c = posColor || '#5cd6a8';
    return `<td style="padding:.2em;text-align:center;color:${c};font-weight:700">●</td>`;
  }
  if (v === false) return `<td style="padding:.2em;text-align:center;color:#333">·</td>`;
  return `<td style="padding:.2em;text-align:center;color:#666">?</td>`;
}

function kvList(obj, fields) {
                                 
  const rows = [];
  for (const [k, label] of fields) {
    if (!(k in obj)) continue;
    let v = obj[k];
    if (v == null || v === '') continue;
    let cls = '';
    let display;
    if (v === true) { cls = 'true'; display = 'true'; }
    else if (v === false) { cls = 'false'; display = 'false'; }
    else if (typeof v === 'object') {
      display = `<code>${escapeHtml(JSON.stringify(v))}</code>`;
    } else {
      display = escapeHtml(String(v));
    }
    rows.push(`<dt>${escapeHtml(label)}</dt><dd class="${cls}">${display}</dd>`);
  }
  if (!rows.length) return '<p class="t-empty">veri yok</p>';
  return `<dl class="kv">${rows.join('')}</dl>`;
}

                                                                             
                             
                                                                             

const TARGET_COUNTRY_NAMES = {
  Turkey:'Türkiye', Greece:'Yunanistan', Egypt:'Mısır', Israel:'İsrail',
  'South Africa':'Güney Afrika', Germany:'Almanya', France:'Fransa',
  Italy:'İtalya', Spain:'İspanya', Portugal:'Portekiz', UK:'Birleşik Krallık',
  'United Kingdom':'Birleşik Krallık', 'United States':'ABD', Canada:'Kanada',
  'Eastern EU':'Doğu Avrupa', 'Central EU':'Orta Avrupa',
  'Saudi Arabia':'Suudi Arabistan', 'Russia (Moscow)':'Rusya (Moskova)',
  'East Africa':'Doğu Afrika', Iceland:'İzlanda', 'West Africa':'Batı Afrika',
  Argentina:'Arjantin', 'Brazil (BR)':'Brezilya (BR)', Suriname:'Surinam',
  'US East':'ABD Doğu', 'Canada East':'Kanada Doğu', Colombia:'Kolombiya', Peru:'Peru',
  'US Pacific':'ABD Pasifik', 'Canada West':'Kanada Batı', Pakistan:'Pakistan',
  Maldives:'Maldivler', India:'Hindistan', 'Sri Lanka':'Sri Lanka', China:'Çin',
  Singapore:'Singapur', Philippines:'Filipinler', 'Australia (Perth)':'Avustralya (Perth)',
  Japan:'Japonya', Korea:'Kore', 'Australia East':'Avustralya Doğu', EU:'Avrupa Birliği',
  Netherlands:'Hollanda', Russia:'Rusya', Ukraine:'Ukrayna', Azerbaijan:'Azerbaycan',
  Iran:'İran', Saudi:'Suudi Arabistan', UAE:'Birleşik Arap Emirlikleri',
  'United Arab Emirates':'Birleşik Arap Emirlikleri',
  Uae:'Birleşik Arap Emirlikleri', USA:'ABD', Usa:'ABD', Uk:'Birleşik Krallık',
};

function targetIntelPresent(value) {
  if (value == null || value === '') return false;
  if (Array.isArray(value)) return value.some(targetIntelPresent);
  if (typeof value === 'object') return Object.values(value).some(targetIntelPresent);
  return true;                               
}

function targetIntelFirst(...values) {
  return values.find(value => value != null && value !== '');
}

function targetIntelFirstItem(value) {
  return Array.isArray(value) && value.length ? value[0] : '';
}

function targetIntelDate(value, withTime=false) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const options = withTime ? {dateStyle:'medium', timeStyle:'short'} : {dateStyle:'long'};
  if (appI18n && typeof appI18n.formatDate === 'function') return appI18n.formatDate(date, options);
  return new Intl.DateTimeFormat('en-US', options).format(date);
}

function targetIntelMonthYear(value) {
  const text = String(value || '').trim();
  if (!text) return '';
  let year;
  let month;
  const normalized = text.toLocaleLowerCase('tr-TR').replace(/\s+/g, ' ').trim();
  const compact = normalized.replace(/[.,]/g, '');
  const chinese = compact.match(/^(\d{4})\s*年\s*(\d{1,2})\s*月$/u);
  const numeric = normalized.match(/^(\d{4})[-/.](\d{1,2})$/u) || normalized.match(/^(\d{1,2})[-/.](\d{4})$/u);
  const names = {
    january:0, jan:0, ocak:0, январь:0, января:0,
    february:1, feb:1, şubat:1, февраль:1, февраля:1,
    march:2, mar:2, mart:2, март:2, марта:2,
    april:3, apr:3, nisan:3, апрель:3, апреля:3,
    may:4, mayıs:4, май:4, мая:4,
    june:5, jun:5, haziran:5, июнь:5, июня:5,
    july:6, jul:6, temmuz:6, июль:6, июля:6,
    august:7, aug:7, ağustos:7, август:7, августа:7,
    september:8, sep:8, sept:8, eylül:8, сентябрь:8, сентября:8,
    october:9, oct:9, ekim:9, октябрь:9, октября:9,
    november:10, nov:10, kasım:10, ноябрь:10, ноября:10,
    december:11, dec:11, aralık:11, декабрь:11, декабря:11,
  };
  if (chinese) {
    year = Number(chinese[1]);
    month = Number(chinese[2]) - 1;
  } else if (numeric) {
    const yearFirst = numeric[1].length === 4;
    year = Number(yearFirst ? numeric[1] : numeric[2]);
    month = Number(yearFirst ? numeric[2] : numeric[1]) - 1;
  } else {
    const words = compact.match(/^([^\d]+?)\s+(\d{4})$/u) || compact.match(/^(\d{4})\s+([^\d]+?)$/u);
    if (words) {
      const yearFirst = /^\d{4}$/.test(words[1]);
      year = Number(yearFirst ? words[1] : words[2]);
      month = names[String(yearFirst ? words[2] : words[1]).trim()];
    }
    if (!Number.isInteger(year) || !Number.isInteger(month)) {
      const parsedFallback = new Date(text);
      if (!Number.isNaN(parsedFallback.getTime())) {
        year = parsedFallback.getFullYear();
        month = parsedFallback.getMonth();
      }
    }
  }
  if (!Number.isInteger(year) || !Number.isInteger(month) || month < 0 || month > 11) return text;
  const parsed = new Date(Date.UTC(year, month, 1));
  if (appI18n && typeof appI18n.formatDate === 'function') {
    return appI18n.formatDate(parsed, {year:'numeric', month:'long', timeZone:'UTC'});
  }
  return new Intl.DateTimeFormat('en-US', {year:'numeric', month:'long', timeZone:'UTC'}).format(parsed);
}

function targetIntelCount(value) {
  return formatUiNumber(value);
}

function targetIntelAccountType(identity) {
  let value = '';
  if (identity.is_business === true) value = 'İşletme hesabı';
  else if (identity.is_professional_account === true) value = 'Profesyonel hesap';
  else value = ({1:'Kişisel hesap', 2:'İçerik üretici hesabı', 3:'İşletme hesabı'})[Number(identity.account_type)]
    || (identity.account_type != null ? 'Hesap türü bilinmiyor' : '');
  return i18nText(value);
}

function targetIntelCountry(value) {
  const country = String(value || '').trim();
  return i18nText(TARGET_COUNTRY_NAMES[country] || country);
}

function targetIntelSafeUrl(value) {
  try {
    const url = new URL(String(value || ''), window.location.origin);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
  } catch (_) {
    return '';
  }
}

function targetIntelFactGrid(rows) {
  const visible = rows.filter(row => row && (row.html || row.value != null && row.value !== ''));
  if (!visible.length) return '';
  return `<div class="ti-facts">${visible.map(row => `
    <div class="ti-fact${row.tone ? ` is-${escapeAttr(row.tone)}` : ''}">
      <span>${escapeHtml(i18nText(row.label))}</span>
      <b${row.mono ? ' class="mono no-i18n"' : row.raw ? ' class="no-i18n"' : ''}>${row.html || escapeHtml(row.raw ? String(row.value) : i18nText(String(row.value)))}</b>
      ${row.note ? `<small>${escapeHtml(i18nText(row.note))}</small>` : ''}
    </div>`).join('')}</div>`;
}

function targetIntelCard({icon, title, description, body, wide=false, tone=''}) {
  if (!body) return '';
  return `<article class="ti-card${wide ? ' ti-card--wide' : ''}${tone ? ` is-${escapeAttr(tone)}` : ''}">
    <header class="ti-card-head">
      <span class="ti-card-icon" aria-hidden="true">${uiIcon(icon || 'info')}</span>
      <div><h3>${escapeHtml(i18nText(title))}</h3>${description ? `<p>${escapeHtml(i18nText(description))}</p>` : ''}</div>
    </header>
    <div class="ti-card-body">${body}</div>
  </article>`;
}

function targetIntelSection(index, title, description, cards) {
  const content = cards.filter(Boolean);
  if (!content.length) return '';
  return `<section class="ti-section">
    <header class="ti-section-head">
      <span>${escapeHtml(index)}</span>
      <div><h2>${escapeHtml(i18nText(title))}</h2><p>${escapeHtml(i18nText(description))}</p></div>
    </header>
    <div class="ti-card-grid">${content.join('')}</div>
  </section>`;
}

function targetIntelMetric(label, value, note='') {
  if (value == null || value === '') return '';
  return `<div class="ti-metric"><span>${escapeHtml(i18nText(label))}</span><b>${escapeHtml(targetIntelCount(value))}</b>${note ? `<small>${escapeHtml(i18nText(note))}</small>` : ''}</div>`;
}

function targetIntelBoolean(value, yes='Evet', no='Hayır') {
  if (typeof value !== 'boolean') return '';
  return i18nText(value ? yes : no);
}

function targetIntelMonths(value) {
  const months = Number(value);
  if (!Number.isFinite(months)) return String(value || '');
  if (months < 12) return i18nT('duration.months', {count:months}, `${formatUiNumber(months)} months`);
  const years = Math.floor(months / 12);
  const rest = months % 12;
  return rest
    ? i18nT('duration.yearsMonths', {years, months:rest}, `${formatUiNumber(years)} years ${formatUiNumber(rest)} months`)
    : i18nT('duration.years', {count:years}, `${formatUiNumber(years)} years`);
}

function renderTargetIntelHuman() {
  const data = state.data || {};
  const ti = data.target_intel || {};
  const root = $('#targetIntel');
  if (!root) return;
  if (!targetIntelPresent(ti)) {
    root.innerHTML = '<div class="ti-empty-state"><b>Profil özeti bulunamadı</b><span>Bu hedef için analizi yeniden çalıştırın.</span></div>';
    translateUi(root);
    return;
  }

  const identity = ti.identity || {};
  const profile = ti.profile || {};
  const privacy = ti.privacy || {};
  const counts = ti.leaked_counts || {};
  const highlights = ti.story_highlights || {};
  const username = data.username || identity.username || state.username || '';
  const fullName = identity.full_name || profile.full_name || '';
  const avatar = ti.avatar || {};
  const avatarUrl = avatar.profile_pic_url || profile.profile_pic_url || '';
  const heroPerson = {
    pk:identity.pk || data.target_pk,
    username,
    full_name:fullName,
    profile_pic_url:avatarUrl,
  };

  const accountType = targetIntelAccountType(identity);
  const heroChips = [];
  if (accountType) heroChips.push(`<span>${escapeHtml(accountType)}</span>`);
  if (typeof privacy.is_private === 'boolean') {
    heroChips.push(`<span class="${privacy.is_private ? 'is-private' : 'is-public'}">${privacy.is_private ? 'Gizli profil' : 'Herkese açık'}</span>`);
  }
  if (typeof privacy.is_verified === 'boolean') {
    heroChips.push(`<span class="${privacy.is_verified ? 'is-verified' : ''}">${privacy.is_verified ? 'Mavi tikli' : 'Mavi tik yok'}</span>`);
  }

  const followers = targetIntelFirst(profile.follower_count, profile.og_follower_count,
    counts.follower_count, counts.gql_followers_total);
  const following = targetIntelFirst(profile.following_count, profile.og_following_count,
    counts.following_count);
  const posts = targetIntelFirst(profile.media_count, profile.og_media_count, counts.media_count);
  const metricHtml = [
    targetIntelMetric('Takipçi', followers),
    targetIntelMetric('Takip', following),
    targetIntelMetric('Gönderi', posts),
    highlights.highlight_count != null ? targetIntelMetric('Öne çıkan', highlights.highlight_count) : '',
  ].filter(Boolean).join('');

  const instagramUrl = `https://www.instagram.com/${encodeURIComponent(username)}/`;
  const threadsUrl = `https://www.threads.net/@${encodeURIComponent(username)}`;
  const hero = `<section class="ti-hero">
    <div class="ti-hero-avatar">${profileAvatar(heroPerson, 'target-intel-photo')}</div>
    <div class="ti-hero-copy">
      <span class="ti-eyebrow">Hedef profil</span>
      <h1>@${escapeHtml(username || '?')}</h1>
      ${fullName ? `<strong>${escapeHtml(fullName)}</strong>` : ''}
      ${heroChips.length ? `<div class="ti-chips">${heroChips.join('')}</div>` : ''}
      ${identity.biography || profile.biography ? `<p>${escapeHtml(identity.biography || profile.biography)}</p>` : ''}
    </div>
    <div class="ti-hero-actions">
      <a href="${escapeAttr(instagramUrl)}" target="_blank" rel="noopener">Instagram ${uiIcon('external-link')}</a>
      <a href="${escapeAttr(threadsUrl)}" target="_blank" rel="noopener">Threads ${uiIcon('external-link')}</a>
    </div>
    ${metricHtml ? `<div class="ti-metric-grid">${metricHtml}</div>` : ''}
    <small class="ti-hero-note">Bilgiler son tamamlanan analiz çıktısından gösteriliyor.</small>
  </section>`;

  const sections = [
    targetIntelSection('01', 'Profil ve hesap', 'Profilde görünen bilgiler ve hesap geçmişi.', [
      renderTargetProfileCard(ti, identity, profile, privacy),
      renderTargetHistoryCard(ti.account_creation || {}),
      renderTargetStoriesCard(highlights),
      renderTargetBioLinksCard(ti.bio_links || []),
    ]),
    targetIntelSection('02', 'Bağlantılar', 'Giriş yaptığınız hesaba göre takip, mesaj ve platform bilgileri.', [
      renderTargetRelationshipCard(ti.friendship || {}),
      renderTargetMessagingCard(ti.dm_state || {}),
      renderTargetBirthdayCard(ti.birthday_oracle || {}),
      renderTargetThreadsCard(ti.cross_platform || {}, privacy, username),
      renderTargetRecoveryCard(ti.recovery || {}),
    ]),
    targetIntelSection('03', 'Analiz sinyalleri', 'Çıkarıma dayalı alanlar kesin bilgi değil, veri işaretleridir.', [
      renderTargetAvatarCard(avatar),
      renderTargetGeoCard(ti.geo_inference || {}, ti.geographic || {}, ti.cdn_forensics || {}),
      renderTargetExtraCountsCard(counts, {followers, following, posts}),
      renderTargetFeaturesCard(ti),
    ]),
    targetIntelSection('04', 'Ayrıntılar', 'Nadiren gereken ağ ve iç kimlik bilgileri.', [
      renderTargetPlatformLinksCard(ti.fb_resolution || {}, username),
      renderTargetTechnicalCard(ti, identity, avatar),
      renderTargetFriendshipGrid(ti.friendship_grid || {}),
    ]),
  ].join('');

  root.innerHTML = `<div class="ti-dashboard">${hero}${sections}</div>`;
  translateUi(root);
}

function renderTargetProfileCard(ti, identity, profile, privacy) {
  const rows = [];
  const accountType = targetIntelAccountType(identity);
  if (accountType) rows.push({label:'Hesap türü', value:accountType, note:'Instagram’ın hesap sınıflandırması.'});
  if (typeof privacy.is_private === 'boolean') rows.push({
    label:'Profil görünürlüğü',
    value:privacy.is_private ? 'Gizli' : 'Herkese açık',
    tone:privacy.is_private ? 'private' : 'positive',
  });
  if (typeof privacy.is_verified === 'boolean') rows.push({
    label:'Instagram rozeti',
    value:privacy.is_verified ? 'Mavi tik var' : 'Mavi tik yok',
    tone:privacy.is_verified ? 'positive' : '',
  });
  if (profile.category_name || profile.category) rows.push({label:'Kategori', value:profile.category_name || profile.category, raw:true});
  if (typeof identity.is_business === 'boolean') rows.push({label:'İşletme hesabı', value:targetIntelBoolean(identity.is_business)});
  if (typeof identity.is_professional_account === 'boolean') rows.push({label:'Profesyonel hesap', value:targetIntelBoolean(identity.is_professional_account)});

  const email = targetIntelFirst(profile.public_email, profile.business_email,
    targetIntelFirstItem(profile.bio_emails_extracted), targetIntelFirstItem(profile.biography_email_addresses));
  const phone = targetIntelFirst(profile.public_phone_number, profile.business_phone_number,
    targetIntelFirstItem(profile.bio_phones_extracted), targetIntelFirstItem(profile.biography_phone_numbers));
  if (email) rows.push({label:'Görünür e-posta', html:`<a class="no-i18n" href="mailto:${escapeAttr(String(email))}">${escapeHtml(String(email))}</a>`});
  if (phone) rows.push({label:'Görünür telefon', html:`<a class="no-i18n" href="tel:${escapeAttr(String(phone))}">${escapeHtml(String(phone))}</a>`});
  const location = [profile.address_street, profile.city_name, profile.zip].filter(Boolean).join(', ');
  if (location) rows.push({label:'Profil adresi', value:location, raw:true, note:'Profilde işletme adresi olarak yayımlanan bilgi.'});
  const externalUrl = targetIntelSafeUrl(profile.external_url);
  if (externalUrl) rows.push({label:'Profil bağlantısı', html:`<a href="${escapeAttr(externalUrl)}" target="_blank" rel="noopener">Bağlantıyı aç ${uiIcon('external-link')}</a>`});

  const biography = identity.biography || profile.biography;
  const body = `${biography ? `<blockquote class="ti-quote no-i18n">${escapeHtml(biography)}</blockquote>` : ''}${targetIntelFactGrid(rows)}`;
  return targetIntelCard({
    icon:'target', title:'Profil bilgileri',
    description:'Instagram yanıtında açıkça görülen temel hesap bilgileri.',
    body,
  });
}

function renderTargetHistoryCard(history) {
  if (!targetIntelPresent(history)) return '';
  const country = targetIntelFirst(history.account_creation_country_text, history.account_creation_country);
  const joined = targetIntelFirst(history.date_joined_iso, history.joined_year_month_text,
    history.account_creation_year_month);
  const former = history.former_usernames;
  const rows = [
    joined ? {label:'Katılma tarihi', value:history.date_joined_iso ? targetIntelDate(joined) : targetIntelMonthYear(joined)} : null,
    country ? {label:'Açıldığı ülke', value:targetIntelCountry(country), note:'Güncel konum anlamına gelmez.'} : null,
    history.account_age_month != null ? {label:'Hesap yaşı', value:targetIntelMonths(history.account_age_month)} : null,
    former != null && former !== '' ? {label:'Önceki kullanıcı adları', value:Array.isArray(former) ? former.join(', ') : former, raw:true} : null,
    history.name_changes_count != null ? {label:'Ad değişikliği', value:targetIntelCount(history.name_changes_count)} : null,
    history.account_takeover_count != null ? {label:'Sahiplik değişikliği kaydı', value:targetIntelCount(history.account_takeover_count), note:'Bu değer tek başına hesap ele geçirilmesi demek değildir.'} : null,
    history.shared_followers_count != null ? {label:'Ortak takipçi', value:targetIntelCount(history.shared_followers_count)} : null,
    typeof history.has_run_ads === 'boolean' ? {label:'Reklam geçmişi', value:history.has_run_ads ? 'Reklam vermiş' : 'Kayıt yok'} : null,
    typeof history.has_run_political_ads === 'boolean' ? {label:'Siyasi reklam', value:history.has_run_political_ads ? 'Kayıt var' : 'Kayıt yok'} : null,
  ];
  return targetIntelCard({
    icon:'clock', title:'Hesap geçmişi',
    description:'DSA, Avrupa Birliği’nin platform şeffaflığı kapsamında sunulan hesap geçmişidir.',
    body:targetIntelFactGrid(rows),
  });
}

function renderTargetStoriesCard(story) {
  const highlights = Array.isArray(story.highlights) ? story.highlights : [];
  const timings = Array.isArray(story.timing_endpoints) ? story.timing_endpoints : [];
  if (story.highlight_count == null && !highlights.length && !timings.length) return '';
  const rows = [
    story.highlight_count != null ? {label:'Öne çıkanlar', value:targetIntelCount(story.highlight_count)} : null,
  ];
  const items = highlights.slice(0, 8).map(item => `<div class="ti-list-item">
    <b class="${item.title ? 'no-i18n' : ''}">${escapeHtml(item.title || i18nText('Başlıksız'))}</b>
    <span>${escapeHtml(i18nT('common.contentCount', {count:item.media_count || 0}, `${targetIntelCount(item.media_count || 0)} items`))}${item.latest_reel_media_iso ? ` · ${escapeHtml(targetIntelDate(item.latest_reel_media_iso))}` : ''}</span>
  </div>`).join('');
  const recent = timings.find(item => item.latest_reel_media_iso || item.expiring_at_iso);
  if (recent) rows.push({
    label:'Son görülen hikâye',
    value:targetIntelDate(recent.latest_reel_media_iso || recent.expiring_at_iso, true),
  });
  return targetIntelCard({
    icon:'image', title:'Hikâyeler ve öne çıkanlar',
    description:'Yalnızca analiz sırasında erişilebilen hikâye ve öne çıkan özetleri.',
    body:`${targetIntelFactGrid(rows)}${items ? `<div class="ti-list">${items}</div>` : ''}`,
  });
}

function renderTargetBioLinksCard(links) {
  if (!Array.isArray(links) || !links.length) return '';
  const items = links.map(link => {
    const url = targetIntelSafeUrl(link.url);
    return `<div class="ti-link-row"><div><b class="${link.title ? 'no-i18n' : ''}">${escapeHtml(link.title || i18nText('Profil bağlantısı'))}</b>${link.link_type ? `<small class="no-i18n">${escapeHtml(link.link_type)}</small>` : ''}</div>${url ? `<a href="${escapeAttr(url)}" target="_blank" rel="noopener">Aç ${uiIcon('external-link')}</a>` : ''}</div>`;
  }).join('');
  return targetIntelCard({
    icon:'external-link', title:'Biyografi bağlantıları',
    description:'Hesabın profilinde yayımlanan dış bağlantılar.',
    body:`<div class="ti-link-list">${items}</div>`,
  });
}

function renderTargetRelationshipCard(friendship) {
  if (!targetIntelPresent(friendship)) return '';
  const hasError = typeof friendship.message === 'string'
    && /sorry|wrong|error|try again/i.test(friendship.message);
  if (hasError) {
    return targetIntelCard({
      icon:'alert-triangle', title:'Takip bağlantısı',
      description:'Giriş yaptığınız hesap ile hedef arasındaki takip durumu.',
      tone:'warning',
      body:'<div class="ti-callout is-warning"><b>Bağlantı bilgisi alınamadı</b><span>Instagram içerikte hata döndürdüğü için bu taramada sonuç üretilmedi.</span></div>',
    });
  }
  const mapping = [
    ['following', 'Bu hesabı takip ediyorsunuz'],
    ['followed_by', 'Bu hesap sizi takip ediyor'],
    ['incoming_request', 'Bu hesaptan takip isteği'],
    ['outgoing_request', 'Bu hesaba gönderilen istek'],
    ['is_bestie', 'Yakın arkadaşlar listesi'],
    ['is_feed_favorite', 'Favoriler akışı'],
    ['muting', 'Sessize alınmış'],
    ['is_restricted', 'Kısıtlanmış'],
    ['blocking', 'Engellenmiş'],
  ];
  const rows = mapping.filter(([key]) => typeof friendship[key] === 'boolean')
    .map(([key, label]) => ({label, value:friendship[key] ? 'Evet' : 'Hayır', tone:friendship[key] ? 'positive' : ''}));
  return targetIntelCard({
    icon:'arrow-left-right', title:'Sizinle bağlantısı',
    description:'“Siz”, uygulamada Instagram’a giriş yapılmış hesabı ifade eder.',
    body:targetIntelFactGrid(rows),
  });
}

function targetIntelResponsivenessLabel(value) {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return '';
  if (normalized.includes('instant') || normalized.includes('immediate')) {
    return i18nT('target.replyImmediate', {}, 'Usually replies almost immediately');
  }
  if (normalized.includes('hour')) {
    return i18nT('target.replyWithinHours', {}, 'Usually replies within a few hours');
  }
  if (normalized.includes('day')) {
    return i18nT('target.replyWithinDay', {}, 'Usually replies within a day');
  }
  if (normalized.includes('week')) {
    return i18nT('target.replyWithinWeek', {}, 'Usually replies within a week');
  }
  if (normalized.includes('fast') || normalized.includes('high')) {
    return i18nT('target.replyFast', {}, 'Usually replies quickly');
  }
  if (normalized.includes('slow') || normalized.includes('low')) {
    return i18nT('target.replySlow', {}, 'Usually takes longer to reply');
  }
  return i18nT('target.replyPatternAvailable', {}, 'Instagram supplied a response-speed category');
}

function renderTargetMessagingCard(dm) {
  if (!targetIntelPresent(dm)) return '';
  const reachability = {
    messageable:'Doğrudan mesaj gönderilebilir',
    message_request:'Mesaj isteği olarak gider',
    blocked:'Mesaj gönderilemiyor',
  }[dm.reachability_status_meaning] || '';
  const rows = [
    reachability ? {label:'Mesaj gönderme', value:reachability} : null,
    typeof dm.is_viewer_unconnected === 'boolean' ? {label:'Mevcut bağlantı', value:dm.is_viewer_unconnected ? 'Bağlantı görünmüyor' : 'Bağlantı var'} : null,
    dm.responsiveness_category ? {label:'Yanıt eğilimi', value:targetIntelResponsivenessLabel(dm.responsiveness_category)} : null,
    typeof dm.should_show_safety_card === 'boolean' ? {label:'Güvenlik uyarısı', value:dm.should_show_safety_card ? 'Gösteriliyor' : 'Gösterilmiyor'} : null,
    typeof dm.has_reached_message_request_limit === 'boolean' ? {label:'Mesaj isteği sınırı', value:dm.has_reached_message_request_limit ? 'Sınıra ulaşılmış' : 'Uygun'} : null,
  ];
  const live = dm.live_presence || {};
  if (typeof live.is_active === 'boolean') rows.push({label:'Şu an aktif', value:live.is_active ? 'Evet' : 'Hayır', tone:live.is_active ? 'positive' : ''});
  if (live.last_activity_iso) rows.push({label:'Son görülme', value:targetIntelDate(live.last_activity_iso, true)});
  const thread = dm.existing_dm_thread || {};
  if (targetIntelPresent(thread)) {
    rows.push({label:'Mevcut konuşma', value:'Var'});
    if (thread.last_activity_iso || thread.last_permanent_item_iso) rows.push({label:'Son konuşma', value:targetIntelDate(thread.last_activity_iso || thread.last_permanent_item_iso, true)});
    if (typeof thread.muted === 'boolean') rows.push({label:'Konuşma sessizde', value:thread.muted ? 'Evet' : 'Hayır'});
  }
  return targetIntelCard({
    icon:'mail', title:'Mesajlaşma durumu',
    description:'Bu durum yalnızca giriş yaptığınız hesabın hedefe göre gördüğü bilgidir.',
    body:targetIntelFactGrid(rows),
  });
}

function renderTargetBirthdayCard(birthday) {
  if (!targetIntelPresent(birthday) || birthday.value === undefined) return '';
  const birthdayState = String(birthday.value || '').trim().toUpperCase();
  const hidden = birthdayState === 'NOT_VISIBLE' || birthdayState === 'NOT_VISIBLE_CLOSE';
  const visibility = hidden ? 'Bu oturumda görünmüyor'
    : birthdayState === 'VISIBLE' ? 'Görünüyor'
      : i18nT('target.birthdayStateAvailable', {}, 'Instagram supplied a birthday visibility state');
  const rows = [
    {label:'Görünürlük', value:visibility},
    !hidden && typeof birthday.has_birthday_data === 'boolean' ? {
      label:'Doğum günü işareti',
      value:birthday.has_birthday_data ? 'Instagram’da mevcut' : 'Bulunamadı',
      note:'Bu işaret tam doğum tarihinin bilindiği anlamına gelmez.',
    } : null,
    !hidden && typeof birthday.birthday_is_today === 'boolean' ? {label:'Bugün mü?', value:birthday.birthday_is_today ? 'Evet' : 'Hayır'} : null,
  ];
  return targetIntelCard({
    icon:'cake', title:'Doğum günü görünürlüğü',
    description:'Instagram’ın bu oturuma gösterdiği sınırlı doğum günü durumu.',
    body:`${hidden ? '<div class="ti-callout"><b>Doğrulanmış tarih yok</b><span>Bu yanıt, doğum gününün bugün olmadığını veya sistemde kesin bir tarih bulunduğunu kanıtlamaz.</span></div>' : ''}${targetIntelFactGrid(rows)}`,
  });
}

function renderTargetThreadsCard(crossPlatform, instagramPrivacy, fallbackUsername) {
  const user = crossPlatform.threads_user || {};
  const hasData = targetIntelPresent(user)
    || crossPlatform.threads_followers_count != null
    || crossPlatform.threads_following_count != null
    || crossPlatform.threads_post_count != null;
  if (!hasData) return '';
  const username = user.username || fallbackUsername;
  const rows = [
    username ? {label:'Kullanıcı adı', value:'@' + username, raw:true} : null,
    typeof user.is_private === 'boolean' ? {label:'Görünürlük', value:user.is_private ? 'Gizli' : 'Herkese açık', tone:user.is_private ? 'private' : 'positive'} : null,
    targetIntelFirst(user.follower_count, crossPlatform.threads_followers_count) != null ? {label:'Takipçi', value:targetIntelCount(targetIntelFirst(user.follower_count, crossPlatform.threads_followers_count))} : null,
    targetIntelFirst(user.following_count, crossPlatform.threads_following_count) != null ? {label:'Takip', value:targetIntelCount(targetIntelFirst(user.following_count, crossPlatform.threads_following_count))} : null,
    targetIntelFirst(user.media_count, crossPlatform.threads_post_count) != null ? {label:'Gönderi', value:targetIntelCount(targetIntelFirst(user.media_count, crossPlatform.threads_post_count))} : null,
  ];
  const visibilityNote = instagramPrivacy.is_private === true && user.is_private === false
    ? '<div class="ti-callout is-warning"><b>Görünürlükler farklı</b><span>Instagram profili gizli, Threads profili ise herkese açık görünüyor.</span></div>' : '';
  const bio = user.biography ? `<blockquote class="ti-quote no-i18n">${escapeHtml(user.biography)}</blockquote>` : '';
  return targetIntelCard({
    icon:'globe', title:'Threads profili',
    description:'Threads ayrı bir platformdur; görünürlük ve sayılar Instagram’dan farklı olabilir.',
    body:`${visibilityNote}${bio}${targetIntelFactGrid(rows)}${username ? `<a class="ti-wide-link" href="https://www.threads.net/@${encodeURIComponent(username)}" target="_blank" rel="noopener">Threads profilini aç ${uiIcon('external-link')}</a>` : ''}`,
  });
}

function renderTargetRecoveryCard(recovery) {
  if (!targetIntelPresent(recovery)) return '';
  const rows = [
    recovery.obfuscated_email ? {label:'Maskeli e-posta', value:recovery.obfuscated_email, raw:true, note:'Tam adres değildir.'} : null,
    recovery.obfuscated_phone ? {label:'Maskeli telefon', value:recovery.obfuscated_phone, raw:true, note:'Tam numara değildir.'} : null,
    typeof recovery.can_email_reset === 'boolean' ? {label:'E-posta ile kurtarma', value:recovery.can_email_reset ? 'Sunuluyor' : 'Sunulmuyor'} : null,
    typeof recovery.can_sms_reset === 'boolean' ? {label:'SMS ile kurtarma', value:recovery.can_sms_reset ? 'Sunuluyor' : 'Sunulmuyor'} : null,
    typeof recovery.two_factor_required === 'boolean' ? {label:'İki adımlı doğrulama', value:recovery.two_factor_required ? 'Gerekli' : 'Gerekli görünmüyor'} : null,
    typeof recovery.has_fb_account_linked === 'boolean' ? {label:'Facebook bağlantısı', value:recovery.has_fb_account_linked ? 'Var' : 'Yok'} : null,
    recovery.rate_limited === true ? {label:'İstek durumu', value:'Instagram geçici olarak sınırladı', tone:'warning'} : null,
  ];
  return targetIntelCard({
    icon:'lock', title:'Hesap kurtarma seçenekleri',
    description:'Instagram’ın maskeleyerek gösterdiği yöntemlerdir; tam iletişim bilgisi değildir.',
    body:targetIntelFactGrid(rows),
  });
}

function renderTargetAvatarCard(avatar) {
  if (!targetIntelPresent(avatar)) return '';
  const rows = [
    avatar.avatar_uploaded_iso ? {
      label:'Tahmini yüklenme tarihi',
      value:targetIntelDate(avatar.avatar_uploaded_iso, true),
      note:'Profil fotoğrafı kimliğindeki zaman bilgisinden çıkarılır.',
    } : null,
    avatar.avatar_age_days != null ? {label:'Fotoğraf yaşı', value:i18nT('target.approxDays', {count:Math.round(Number(avatar.avatar_age_days))}, `About ${targetIntelCount(Math.round(Number(avatar.avatar_age_days)))} days`)} : null,
    typeof avatar.uploader_matches_target === 'boolean' ? {
      label:'Hesapla eşleşme',
      value:avatar.uploader_matches_target ? 'Fotoğraf kimliği hesapla eşleşiyor' : 'Eşleşme görülmedi',
      tone:avatar.uploader_matches_target ? 'positive' : 'warning',
    } : null,
    typeof avatar.stolen_avatar_signal === 'boolean' ? {
      label:'Başka hesap izi',
      value:avatar.stolen_avatar_signal ? 'Farklı hesap kimliğiyle eşleşme var' : 'Görülmedi',
      note:'Bu yalnız teknik bir işarettir; fotoğrafın çalındığını kanıtlamaz.',
      tone:avatar.stolen_avatar_signal ? 'warning' : 'positive',
    } : null,
  ];
  if (!rows.some(Boolean)) return '';
  const technical = avatar.media_id || avatar.hex ? `<details class="ti-inline-details">
    <summary>Fotoğrafın teknik kimlikleri</summary>
    ${targetIntelFactGrid([
      avatar.media_id ? {label:'Meta içerik kimliği', value:avatar.media_id, mono:true, note:'Fotoğraf kaydının dahili numarasıdır.'} : null,
      avatar.hex ? {label:'Kodlanmış kimlik', value:avatar.hex, mono:true, note:'Aynı numaranın onaltılık gösterimidir.'} : null,
    ])}
  </details>` : '';
  return targetIntelCard({
    icon:'image', title:'Profil fotoğrafı sinyalleri',
    description:'Fotoğrafın içerik kimliğinden çıkarılan zaman ve sahiplik işaretleri.',
    body:`${targetIntelFactGrid(rows)}${technical}`,
  });
}

function targetIntelConfidence(value) {
  const label = ({high:'Güçlü', medium:'Orta', low:'Zayıf', none:'Yetersiz'})[String(value || '').toLowerCase()]
    || 'Belirsiz';
  return i18nText(label);
}

function renderTargetGeoCard(geoInference, rawGeo, cdn) {
  const final = geoInference.final_inference || {};
  const timezone = geoInference.timezone_inference || {};
  const tagged = geoInference.tagged_locations || {};
  const biography = geoInference.bio_text_matches || {};
  const language = geoInference.cluster_language_distribution || {};
  const avatarHours = geoInference.avatar_upload_histogram || {};
  const candidates = Object.entries(final.all_candidates || {})
    .map(([country, score]) => [country, Number(score) || 0])
    .sort((a, b) => b[1] - a[1]);
  const hasSignal = final.best_country_guess || candidates.length
    || Number(timezone.sample_count) > 0 || Number(tagged.distinct_count) > 0
    || (biography.matches || []).length || Number(language.sample_size) > 0
    || Number(avatarHours.decoded_count) > 0;
  if (!hasSignal) return '';

  const topScore = candidates.length ? candidates[0][1] : Number(final.best_score) || 0;
  const tied = candidates.filter(([, score]) => Math.abs(score - topScore) < 0.000001);
  const confidenceKey = String(final.confidence || 'none').toLowerCase();
  const uncertain = !final.best_country_guess || tied.length > 1 || ['low', 'none'].includes(confidenceKey);
  const leadCountry = targetIntelCountry(final.best_country_guess || (candidates[0] || [])[0]);
  const result = uncertain ? i18nText('Konum belirsiz') : leadCountry;
  const summary = uncertain
    ? `${tied.length > 1
      ? i18nText('Birden fazla ülke aynı güçte.')
      : leadCountry
        ? i18nT('target.geoWeakCandidate', {country:leadCountry}, `Strongest candidate: ${leadCountry}, but the signal is weak.`)
        : i18nText('Yeterli işaret yok.')}`
    : i18nT('target.geoLead', {country:leadCountry}, `Strongest candidate: ${leadCountry}.`);
  const confidence = targetIntelConfidence(final.confidence);

  const signalRows = [
    Number(timezone.sample_count) > 0 ? {label:'Zaman örneği', value:i18nT('common.recordCount', {count:timezone.sample_count}, `${targetIntelCount(timezone.sample_count)} records`), note:'Az örnek, sonucu güvenilmez yapabilir.'} : null,
    timezone.estimated_local_timezone ? {label:'Saat dilimi ipucu', value:timezone.estimated_local_timezone, note:'Etkinlik saatlerinden tahmin edilir.'} : null,
    Number(tagged.distinct_count) > 0 ? {label:'Etiketli konum', value:i18nT('target.distinctPlaces', {count:tagged.distinct_count}, `${targetIntelCount(tagged.distinct_count)} distinct places`), note:'İkamet adresi anlamına gelmez.'} : null,
    (biography.matches || []).length ? {label:'Biyografi eşleşmesi', value:i18nT('target.textClues', {count:biography.matches.length}, `${targetIntelCount(biography.matches.length)} text clues`)} : null,
    Number(language.sample_size) > 0 && Number(language.turkish_combined_accounts) > 0 ? {
      label:'İlişkili ağın dili',
      value:i18nT('target.turkishAccounts', {
        found:language.turkish_combined_accounts, total:language.sample_size,
      }, `${targetIntelCount(language.turkish_combined_accounts)} / ${targetIntelCount(language.sample_size)} accounts show Turkish-language clues`),
      note:'Türkçe konuşan bir ağ, hedefin Türkiye’de yaşadığını kanıtlamaz.'
    } : null,
    Number(avatarHours.decoded_count) > 0 ? {
      label:'Ağdaki fotoğraf saatleri',
      value: targetIntelPresent(avatarHours.cluster_size)
        ? i18nT('target.decodedOf', {found:avatarHours.decoded_count, total:avatarHours.cluster_size}, `${targetIntelCount(avatarHours.decoded_count)} / ${targetIntelCount(avatarHours.cluster_size)} decoded`)
        : i18nT('target.decodedHours', {count:avatarHours.decoded_count}, `${targetIntelCount(avatarHours.decoded_count)} time records decoded`),
      note:'Hedefin kendi konumu değildir.'
    } : null,
  ];

  const maxScore = Math.max(0.000001, ...candidates.map(([, score]) => score));
  const candidateHtml = candidates.length ? `<details class="ti-inline-details ti-geo-candidates">
    <summary>Ülke adaylarını ve göreli skorları göster</summary>
    <p class="ti-detail-note">Bu skorlar olasılık yüzdesi değildir; farklı işaretlerin göreli ağırlığıdır.</p>
    <div class="ti-bars">${candidates.slice(0, 8).map(([country, score]) => `
      <div class="ti-bar-row">
        <span>${escapeHtml(targetIntelCountry(country))}</span>
        <i><b style="width:${Math.max(2, score / maxScore * 100).toFixed(1)}%"></b></i>
        <em>${escapeHtml(formatUiNumber(score, {maximumFractionDigits:2}))}</em>
      </div>`).join('')}</div>
  </details>` : '';

  const topLocations = (tagged.top_locations || []).slice(0, 5);
  const locationsHtml = topLocations.length ? `<div class="ti-subsection">
    <b>Etiketlerde görülen yerler</b>
    <div class="ti-place-list">${topLocations.map(place => {
      const coordinates = place.lat != null && place.lng != null
        && Number.isFinite(Number(place.lat)) && Number.isFinite(Number(place.lng));
      const mapUrl = coordinates ? `https://www.google.com/maps?q=${encodeURIComponent(`${place.lat},${place.lng}`)}` : '';
      const placeName = String(place.name || place.city || i18nT('target.unnamedLocation', {}, 'Unnamed location'));
      const placeCity = String(place.city || '');
      const recordCount = Number(place.count);
      const hasRecordCount = place.count !== undefined && place.count !== null
        && Number.isFinite(recordCount) && recordCount > 0;
      const placeMeta = placeCity && hasRecordCount
        ? i18nT('target.placeRecordCount', {place:placeCity, count:recordCount}, `${placeCity} · ${recordCount} records`)
        : placeCity || (hasRecordCount
          ? i18nT('common.recordCount', {count:recordCount}, `${recordCount} records`)
          : '');
      return `<div><span class="no-i18n">${escapeHtml(placeName)}</span><small class="no-i18n">${escapeHtml(placeMeta)}</small>${mapUrl ? `<a href="${escapeAttr(mapUrl)}" target="_blank" rel="noopener">Harita ${uiIcon('external-link')}</a>` : ''}</div>`;
    }).join('')}</div>
  </div>` : '';

  const bioMatches = (biography.matches || []).slice(0, 6);
  const bioHtml = bioMatches.length ? `<div class="ti-subsection">
    <b>Biyografideki yer işaretleri</b>
    <div class="ti-chips">${bioMatches.map(match => `<span>${escapeHtml(match.value || '?')} → ${escapeHtml(targetIntelCountry(match.country_hint || '?'))}</span>`).join('')}</div>
  </div>` : '';

  const chart = avatarHours.hour_histogram_utc
    ? `<div class="ti-subsection"><b>Ağdaki profil fotoğrafı yükleme saatleri (UTC / evrensel saat)</b>${renderTargetHourBars(avatarHours.hour_histogram_utc, avatarHours.peak_window_utc)}<small>Bu grafik yalnız ağdaki genel saat dağılımıdır; hedefin saat dilimini kanıtlamaz.</small></div>`
    : timezone.hour_histogram_utc ? `<div class="ti-subsection"><b>Görülen etkinlik saatleri (UTC / evrensel saat)</b>${renderTargetHourBars(timezone.hour_histogram_utc)}<small>Az sayıda kayıt varsa yalnız zayıf bir zaman ipucudur.</small></div>` : '';

  const viewerNotes = [];
  if (rawGeo.html_lang || (rawGeo.signals || []).some(item => String(item).includes('html_lang='))) {
    viewerNotes.push('Sayfa dili oturuma/tarayıcıya aittir; hedefin ülkesini göstermez.');
  }
  if (cdn.cdn_region_code || cdn.cdn_region_hint) {
    viewerNotes.push('CDN bölgesi isteği karşılayan sunucudur; hedefin konumu değildir.');
  }

  const body = `<div class="ti-geo-result${uncertain ? ' is-uncertain' : ''}">
      <div><span>Yaklaşık sonuç</span><strong>${escapeHtml(result || 'Konum belirsiz')}</strong><p>${escapeHtml(summary)}</p></div>
      <b>${escapeHtml(i18nT('target.confidenceValue', {confidence}, `${confidence} confidence`))}</b>
    </div>
    <div class="ti-callout${uncertain ? ' is-warning' : ''}"><b>Kesin konum değildir</b><span>Saat, biyografi, etiket ve ilişkili ağın dili gibi işaretlerin birleşiminden oluşan tahmindir.</span></div>
    ${targetIntelFactGrid(signalRows)}${candidateHtml}${locationsHtml}${bioHtml}${chart}
    ${viewerNotes.length ? `<div class="ti-note-list">${viewerNotes.map(note => `<span>${escapeHtml(note)}</span>`).join('')}</div>` : ''}`;
  return targetIntelCard({
    icon:'map-pin', title:'Yaklaşık bölge tahmini',
    description:'Birden fazla zayıf işaret birlikte değerlendirilir; tek başına hiçbiri konum kanıtı değildir.',
    body, wide:true, tone:uncertain ? 'warning' : 'positive',
  });
}

function renderTargetHourBars(histogram, peakWindow) {
  const values = Array.from({length:24}, (_, hour) => Number(histogram[String(hour)] || 0));
  const max = Math.max(1, ...values);
  const peaks = new Set();
  if (Array.isArray(peakWindow) && peakWindow.length === 2) {
    const start = Number(peakWindow[0]);
    const end = Number(peakWindow[1]);
    for (let hour = 0; hour < 24; hour++) {
      if (end >= start ? hour >= start && hour <= end : hour >= start || hour <= end) peaks.add(hour);
    }
  }
  return `<div class="ti-hour-chart" aria-label="${escapeAttr(i18nT('target.hourChartAria', {}, '24-hour distribution'))}">${values.map((value, hour) => `
    <i class="${peaks.has(hour) ? 'is-peak' : ''}" style="--hour-height:${Math.max(2, value / max * 100).toFixed(1)}%" title="${escapeAttr(i18nT('target.hourRecordTitle', {hour, count:value}, `UTC ${hour}:00 · ${value} records`))}"><span>${hour % 3 === 0 ? hour : ''}</span></i>`).join('')}</div>`;
}

function renderTargetExtraCountsCard(counts, primary) {
  const rows = [];
  if (counts.gql_followers_total != null && String(counts.gql_followers_total) !== String(primary.followers)) {
    rows.push({label:'Takipçi (alternatif kaynak)', value:targetIntelCount(counts.gql_followers_total), note:'Başka bir Instagram yanıtından geldiği için ana sayıyla farklı olabilir.'});
  }
  if (counts.usertags_count != null) rows.push({label:'Etiketlendiği içerik', value:targetIntelCount(counts.usertags_count)});
  if (counts.total_clips_count != null) rows.push({label:'Reels / kısa video', value:targetIntelCount(counts.total_clips_count)});
  if (counts.total_igtv_videos != null) rows.push({label:'Uzun video', value:targetIntelCount(counts.total_igtv_videos)});
  if (counts.mutual_followers_count != null) {
    rows.push({
      label:'Test hesabıyla ortak takipçi',
      value:targetIntelCount(counts.mutual_followers_count),
      note:'Bu sayı sorgulanan hedefe değil, giriş yapılan test hesabına göredir.',
    });
  }
  if (!rows.length) return '';
  return targetIntelCard({
    icon:'list', title:'Diğer profil sayıları',
    description:'Farklı Instagram yanıtlarında bulunan ek sayılar; aynı anda güncellenmemiş olabilir.',
    body:targetIntelFactGrid(rows),
  });
}

function targetPromptLabel(prompt) {
  const labels = {
    CURRENT_OBSESSION:'Şu anki ilgim', DREAM_DESTINATION:'Hayalimdeki yer',
    PLAYING:'Oynadığım', READING:'Okuduğum', WATCHING:'İzlediğim',
    LOOKING_FOR_RECS:'Öneri arıyorum',
  };
  return labels[prompt.prompt]
    ? i18nText(labels[prompt.prompt])
    : (prompt.display_text || prompt.prompt || i18nText('Soru şablonu'));
}

function renderTargetFeaturesCard(ti) {
  const behavior = ti.behavior_toggles || {};
  const privacy = ti.privacy || {};
  const prefs = ti.personal_prefs || {};
  const monetization = ti.monetization || {};
  const rows = [];
  const recommendations = behavior.recs_from_friends || (ti.extras || {}).recs_from_friends;
  if (recommendations && typeof recommendations.enable_recs_from_friends === 'boolean') {
    rows.push({label:'Arkadaş önerileri', value:recommendations.enable_recs_from_friends ? 'Açık görünüyor' : 'Kapalı görünüyor'});
  }
  if (behavior.views_on_grid_status) rows.push({
    label:'Izgara görüntülenmeleri',
    value:behavior.views_on_grid_status === 'SHOW_VIEWS_ON_GRID' ? 'Gösterilebilir' : 'Gizli / bilinmiyor',
  });
  const insights = targetIntelFirst(behavior.show_post_insights_entry_point, privacy.show_post_insights_entry_point);
  if (typeof insights === 'boolean') rows.push({label:'Gönderi istatistikleri', value:insights ? 'Menü işareti mevcut' : 'Menü işareti yok'});
  if (typeof behavior.should_show_tagged_tab === 'boolean') rows.push({label:'Etiketlenenler sekmesi', value:behavior.should_show_tagged_tab ? 'Gösterilebilir' : 'Gizli'});
  if (typeof behavior.has_public_tab_threads === 'boolean') rows.push({label:'Profilde Threads sekmesi', value:behavior.has_public_tab_threads ? 'Mevcut' : 'Yok'});
  if (typeof privacy.show_account_transparency_details === 'boolean') rows.push({label:'Hesap şeffaflığı', value:privacy.show_account_transparency_details ? 'Bölüm mevcut' : 'Bölüm görünmüyor'});
  if (typeof behavior.include_direct_blacklist_status === 'boolean') rows.push({label:'Mesaj filtreleme bilgisi', value:behavior.include_direct_blacklist_status ? 'Bilgi görüldü' : 'Bulunmadı'});

  const paidSignals = [];
  if (monetization.is_meta_verified_subscription_holder === true) paidSignals.push('Meta Verified aboneliği');
  if (monetization.is_eligible_for_meta_verified_label === true) paidSignals.push('Meta Verified uygunluğu');
  if (monetization.has_subscription_offers === true) paidSignals.push('Abonelik teklifi');
  const fanCount = monetization.fan_club_info && monetization.fan_club_info.subscriber_count;
  if (Number(fanCount) > 0) paidSignals.push(i18nT('target.paidSubscribers', {count:fanCount}, `${targetIntelCount(fanCount)} paid subscribers`));
  if ((monetization.active_standalone_fundraisers || []).length) paidSignals.push('Aktif bağış kampanyası');

  const prompts = Array.isArray(prefs.qa_banner_prompts) ? prefs.qa_banner_prompts : [];
  const nametag = prefs.nametag || {};
  const extras = `${nametag.emoji ? `<div class="ti-preference"><span>${escapeHtml(nametag.emoji)}</span><div><b>Profil etiketi emojisi</b><small>Instagram nametag tasarımında görülen emoji.</small></div></div>` : ''}
    ${prompts.length ? `<div class="ti-subsection"><b>Kullanılabilir soru şablonları</b><div class="ti-chips">${prompts.map(prompt => `<span class="no-i18n">${escapeHtml(targetPromptLabel(prompt))}</span>`).join('')}</div><small>Bunlar kullanıcının verdiği cevaplar değil, Instagram’ın sunduğu hazır seçeneklerdir.</small></div>` : ''}
    ${paidSignals.length ? `<div class="ti-subsection"><b>Abonelik ve gelir özellikleri</b><div class="ti-chips">${paidSignals.map(item => `<span>${escapeHtml(item)}</span>`).join('')}</div></div>` : ''}`;
  const body = `${targetIntelFactGrid(rows)}${extras}`;
  if (!body.trim()) return '';
  return targetIntelCard({
    icon:'sparkles', title:'Instagram özellikleri',
    description:'Bu göstergeler bir özelliğin sunulabildiğini gösterir; kullanıcının seçimini her zaman kanıtlamaz.',
    body,
  });
}

function renderTargetPlatformLinksCard(facebook, username) {
  const candidates = Array.isArray(facebook.fb_profile_candidates) ? facebook.fb_profile_candidates : [];
  if (!candidates.length && !facebook.result) return '';
  const noSignal = facebook.result === 'no_real_fb_profile_signal';
  const body = `${noSignal ? '<div class="ti-callout"><b>Bu taramada doğrulanmış Facebook bağlantısı bulunmadı</b><span>Meta iç kimlikleri herkese açık Facebook profil numarası değildir.</span></div>' : ''}
    ${candidates.length ? `<div class="ti-link-list">${candidates.map(candidate => {
      const url = targetIntelSafeUrl(candidate.url);
      return `<div class="ti-link-row"><div><b>Facebook profil adayı</b><small>Aynı kişi olduğu doğrulanmamıştır.</small></div>${url ? `<a href="${escapeAttr(url)}" target="_blank" rel="noopener">Aç ${uiIcon('external-link')}</a>` : ''}</div>`;
    }).join('')}</div>` : ''}`;
  return targetIntelCard({
    icon:'globe', title:'Olası Facebook bağlantıları',
    description:i18nT('target.facebookCandidatesFor', {username:`@${username}`}, `Links found for @${username} are only candidates, not verified identity matches.`),
    body,
  });
}

function renderTargetTechnicalCard(ti, identity, avatar) {
  const meta = ti.meta_ids || {};
  const cdn = ti.cdn_forensics || {};
  const headers = ti.header_forensics || {};
  const rows = [
    targetIntelFirst(identity.pk, state.data && state.data.target_pk) ? {label:'Instagram hesap kimliği', value:targetIntelFirst(identity.pk, state.data && state.data.target_pk), mono:true, note:'Instagram’ın hesaba verdiği dahili numara.'} : null,
    targetIntelFirst(meta.fbid_v2, identity.fbid_v2) ? {label:'Meta profil kimliği', value:targetIntelFirst(meta.fbid_v2, identity.fbid_v2), mono:true, note:'Herkese açık Facebook profil numarası değildir.'} : null,
    targetIntelFirst(meta.interop_messaging_user_fbid, identity.interop_messaging_user_fbid) ? {label:'Mesajlaşma kimliği', value:targetIntelFirst(meta.interop_messaging_user_fbid, identity.interop_messaging_user_fbid), mono:true, note:'Meta uygulamaları arasındaki dahili mesajlaşma numarası.'} : null,
    identity.eimu_id ? {label:'Birleşik Meta kimliği', value:identity.eimu_id, mono:true, note:'Platformlar arası dahili eşleştirme anahtarı.'} : null,
    cdn.cdn_region_hint || cdn.cdn_region_code ? {label:'İsteği karşılayan CDN', value:cdn.cdn_region_hint || cdn.cdn_region_code, note:'Hedefin konumu değil, isteğin ulaştığı Meta sunucusudur.'} : null,
    cdn.oe_expires_iso ? {label:'Fotoğraf bağlantısı geçerliliği', value:targetIntelDate(cdn.oe_expires_iso, true)} : null,
    headers.target_context && Object.keys(headers.target_context).length ? {label:'Yanıt tanılama başlığı', value:'Mevcut', note:'Hata ayıklama içindir; kişi bilgisi değildir.'} : null,
  ];
  if (!rows.some(Boolean)) return '';
  return targetIntelCard({
    icon:'code', title:'Teknik kimlikler ve ağ bilgisi',
    description:'Bu numara ve sunucu işaretleri uygulamanın çalışması içindir; kişisel profil veya konum kanıtı değildir.',
    body:`<details class="ti-inline-details"><summary>Teknik değerleri göster</summary>${targetIntelFactGrid(rows)}</details>`,
  });
}

function targetFriendshipCell(value) {
  if (value === true) return '<span class="ti-table-state is-yes">Evet</span>';
  if (value === false) return '<span class="ti-table-state is-no">Hayır</span>';
  return '<span class="ti-table-state">—</span>';
}

function renderTargetFriendshipGrid(grid) {
  const rows = Array.isArray(grid.rows) ? grid.rows : [];
  if (!rows.length) return '';
  const count = key => rows.filter(row => row[key] === true).length;
  const summary = [
    targetIntelMetric('Test hesabının takip ettiği', count('fs_following')),
    targetIntelMetric('Test hesabını takip eden', count('fs_followed_by')),
    targetIntelMetric('Gizli profil', rows.filter(row => row.is_private === true).length),
    targetIntelMetric('Mavi tikli', rows.filter(row => row.is_verified === true).length),
  ].join('');
  const tableRows = rows.slice(0, 60).map(row => {
    const flags = [];
    if (row.fs_is_bestie) flags.push(i18nT('signal.closeFriend', {}, 'Close friend'));
    if (row.fs_is_feed_favorite) flags.push(i18nT('target.favoriteShort', {}, 'Favorite'));
    if (row.fs_incoming_request) flags.push(i18nT('target.requestSent', {}, 'Requested the test account'));
    if (row.fs_outgoing_request) flags.push(i18nT('target.youSentRequest', {}, 'Test account requested'));
    if (row.fs_muting) flags.push(i18nT('target.mutedShort', {}, 'Muted'));
    if (row.fs_is_restricted) flags.push(i18nT('target.restrictedShort', {}, 'Restricted'));
    if (row.fs_blocking) flags.push(i18nT('target.blockedShort', {}, 'Blocked'));
    return `<tr>
      <td><a class="no-i18n" href="https://www.instagram.com/${encodeURIComponent(row.username || '')}/" target="_blank" rel="noopener">@${escapeHtml(row.username || '?')}</a>${row.full_name ? `<small class="no-i18n">${escapeHtml(row.full_name)}</small>` : ''}</td>
      <td>${targetFriendshipCell(row.fs_following)}</td>
      <td>${targetFriendshipCell(row.fs_followed_by)}</td>
      <td>${row.is_private === true ? 'Gizli' : row.is_private === false ? 'Açık' : '—'}</td>
      <td>${flags.length ? escapeHtml(flags.join(' · ')) : '—'}</td>
    </tr>`;
  }).join('');
  return `<details class="ti-card ti-card--wide ti-network-card">
    <summary>
      <span class="ti-card-icon" aria-hidden="true">${uiIcon('network')}</span>
      <div><h3>Test hesabının öneri ağındaki durumlar</h3><p>Bu liste hedefin arkadaşları değildir; yalnızca giriş yapılan test hesabının öneri kümesine göre durumları gösterir.</p></div>
      <b>${targetIntelCount(rows.length)}</b>
    </summary>
    <div class="ti-network-body">
      <div class="ti-metric-grid is-compact">${summary}</div>
      <div class="ti-table-wrap"><table class="ti-network-table"><thead><tr><th>Kullanıcı</th><th>Test hesabı takip ediyor</th><th>Test hesabını takip ediyor</th><th>Profil</th><th>Diğer durumlar</th></tr></thead><tbody>${tableRows}</tbody></table></div>
      ${rows.length > 60 ? `<small class="ti-table-note">${escapeHtml(i18nT('target.moreAccounts', {count:rows.length - 60}, `First 60 accounts shown; ${targetIntelCount(rows.length - 60)} more.`))}</small>` : ''}
    </div>
  </details>`;
}

                                                                             
                           
                                                                             

const PHASE_DEFS = [
  {key:'presence',    labelKey:'phase.presence',    descKey:'phase.approx2m'},
  {key:'dsa',         labelKey:'phase.dsa',         descKey:'phase.often404'},
  {key:'inflate',     labelKey:'phase.inflate',     descKey:'phase.often404'},
  {key:'archeology',  labelKey:'phase.archeology',  descKey:'phase.approx2to5m'},
  {key:'tagged',      labelKey:'phase.tagged',      descKey:'phase.approx1m'},
  {key:'news',        labelKey:'phase.news',        descKey:'phase.approx30s'},
  {key:'chain',       labelKey:'phase.chain',       descKey:'phase.approx10s'},
  {key:'internal',    labelKey:'phase.internal',    descKey:'phase.approx30s'},
  {key:'followgraph', labelKey:'phase.followgraph', descKey:'phase.approx30s'},
  {key:'reciprocal',  labelKey:'phase.reciprocal',  descKey:'phase.approx30s'},
  {key:'banyan',      labelKey:'phase.banyan',      descKey:'phase.approx10s'},
];

const FAST_PHASES = ['presence','chain','internal','reciprocal','banyan'];

const queryState = {
  selectedPhases: new Set(FAST_PHASES),
  evtSource: null,
  username: null,
  chainMulti: 5,
  runId: 0,
  logKeys: new Set(),
  logEntries: new Map(),
  logHistory: [],
  logMeta: null,
};

const LOG_PHASE_COPY = {
  26: {title:'Profil ve erişim bilgileri inceleniyor', detail:'Takip, mesajlaşma ve profil görünürlüğü kontrol ediliyor.', progress:18},
  27: {title:'Hesap geçmişi kontrol ediliyor', detail:'Hesabın açılış ve şeffaflık bilgileri aranıyor.', progress:27},
  28: {title:'Profil alanları taranıyor', detail:'Instagram’ın sunduğu ek profil bilgileri kontrol ediliyor.', progress:35},
  29: {title:'Eski etkinlik izleri inceleniyor', detail:'Erişilebilen geçmiş etkinlik işaretleri aranıyor.', progress:43},
  30: {title:'Etiketli içerikler inceleniyor', detail:'Profilin etiketlendiği erişilebilir içerikler kontrol ediliyor.', progress:50},
  31: {title:'Mesaj kutusu işaretleri inceleniyor', detail:'Giriş yaptığınız hesaba göre görülebilen bağlantılar aranıyor.', progress:56},
  32: {title:'Bağlantı adayları toplanıyor', detail:'İlişkili hesap ağı birleştiriliyor.', progress:64},
  33: {title:'Hesap ayrıntıları kontrol ediliyor', detail:'Hedef profil için bulunan bilgiler düzenleniyor.', progress:72},
  34: {title:'Takip ağı inceleniyor', detail:'Erişilebilen takip bağlantıları karşılaştırılıyor.', progress:78},
  35: {title:'Karşılıklı öneri örtüşmesi inceleniyor', detail:'Öneri zincirinin iki yönünde görülen adaylar karşılaştırılıyor; bu takip kanıtı değildir.', progress:84},
  37: {title:'Etkileşim yakınlığı kontrol ediliyor', detail:'Paylaşım önerileri giriş yaptığınız hesaba göre değerlendiriliyor.', progress:88},
};

function buildPhaseList() {
  const c = $('#phaseList');
  c.innerHTML = PHASE_DEFS.map(p => `
    <label>
      <input type="checkbox" class="phase-chk" value="${p.key}"
             ${queryState.selectedPhases.has(p.key) ? 'checked' : ''}>
      <span>${escapeHtml(i18nT(p.labelKey, {}, p.key))} <span class="muted">${escapeHtml(i18nT(p.descKey, {}, ''))}</span></span>
    </label>`).join('');
  $$('.phase-chk').forEach(c => c.addEventListener('change', () => {
    if (c.checked) queryState.selectedPhases.add(c.value);
    else queryState.selectedPhases.delete(c.value);
  }));
  translateUi(c);
}

function syncPhaseChecks() {
  $$('.phase-chk').forEach(c => {
    c.checked = queryState.selectedPhases.has(c.value);
  });
}

function appendRawLog(text, cls='') {
  const pre = $('#logRawPre');
  if (!pre) return;
  const span = document.createElement('span');
  if (cls) span.className = cls;
  span.textContent = text + '\n';
  pre.appendChild(span);
  pre.scrollTop = pre.scrollHeight;
}

function setLogProgress(title, detail='', progress=null, tone='info') {
  const overview = $('#logOverview');
  const titleEl = $('#logProgressTitle');
  const detailEl = $('#logProgressText');
  const statusEl = $('#logStatus');
  const progressEl = $('#logProgress');
  const bar = $('#logProgressBar');
  const localizedTitle = i18nText(title || '');
  const localizedDetail = i18nText(detail || '');
  if (titleEl) titleEl.textContent = localizedTitle;
  if (detailEl) detailEl.textContent = localizedDetail;
  if (statusEl) statusEl.textContent = localizedTitle;
  if (overview) {
    overview.className = `log-overview is-${tone}`;
    const mark = overview.querySelector('.log-overview-mark');
    if (mark) mark.innerHTML = uiIcon(({ok:'check', warn:'alert-triangle', err:'close', work:'refresh', info:'info'})[tone] || 'info');
  }
  if (progress != null && Number.isFinite(Number(progress))) {
    const current = Number(progressEl && progressEl.getAttribute('aria-valuenow')) || 0;
    const value = Math.max(current, Math.max(0, Math.min(100, Number(progress))));
    if (bar) bar.style.width = `${value}%`;
    if (progressEl) progressEl.setAttribute('aria-valuenow', String(Math.round(value)));
  }
}

function appendHumanLog(event, {remember=true}={}) {
  if (!event || !event.title) return;
  const feed = $('#logPre');
  if (!feed) return;
  const key = event.key || '';
  if (remember) {
    const historyIndex = key ? queryState.logHistory.findIndex(item => item.key === key) : -1;
    if (historyIndex >= 0 && event.update) queryState.logHistory[historyIndex] = {...event};
    else if (historyIndex < 0) queryState.logHistory.push({...event});
  }
  const localizedTitle = i18nText(event.title);
  const localizedDetail = event.tierCounts
    ? formatTierCounts(event.tierCounts)
    : i18nText(event.detail || '');
  const existing = key ? queryState.logEntries.get(key) : null;
  if (existing) {
    if (event.update) {
      existing.querySelector('b').textContent = localizedTitle;
      const detail = existing.querySelector('small');
      if (detail) detail.textContent = localizedDetail;
      existing.className = `log-event l-${event.tone || 'info'}`;
      setLogProgress(localizedTitle, localizedDetail, event.progress, event.tone || 'info');
    }
    return;
  }
  if (key) queryState.logKeys.add(key);
  const row = document.createElement('div');
  row.className = `log-event l-${event.tone || 'info'}`;
  const mark = document.createElement('span');
  mark.className = 'log-event-mark';
  mark.setAttribute('aria-hidden', 'true');
  mark.innerHTML = uiIcon(({ok:'check', warn:'alert-triangle', err:'close', work:'refresh', info:'info'})[event.tone] || 'info');
  const copy = document.createElement('div');
  const heading = document.createElement('b');
  heading.textContent = localizedTitle;
  const detail = document.createElement('small');
  detail.textContent = localizedDetail;
  copy.append(heading, detail);
  row.append(mark, copy);
  feed.appendChild(row);
  if (key) queryState.logEntries.set(key, row);
  setLogProgress(localizedTitle, localizedDetail, event.progress, event.tone || 'info');
  feed.scrollTop = feed.scrollHeight;
  translateUi(row);
}

function rerenderHumanLogs() {
  const feed = $('#logPre');
  if (!feed) return;
  const history = queryState.logHistory.slice();
  feed.innerHTML = '';
  queryState.logKeys = new Set();
  queryState.logEntries = new Map();
  const progress = $('#logProgress');
  if (progress) progress.setAttribute('aria-valuenow', '0');
  const bar = $('#logProgressBar');
  if (bar) bar.style.width = '0%';
  history.forEach(event => appendHumanLog(event, {remember:false}));
}

function formatTierCounts(counts) {
  if (!counts || typeof counts !== 'object') {
    return i18nT('log.groupedByProbability', {}, 'People were grouped by model confidence.');
  }
  const labels = [
    ['verified', localizedTierLabel('verified', {short:true})],
    ['high_probability', localizedTierLabel('high_probability', {short:true})],
    ['medium_probability', localizedTierLabel('medium_probability', {short:true})],
    ['low_probability', localizedTierLabel('low_probability', {short:true})],
    ['noise', localizedTierLabel('noise', {short:true})],
    ['unknown', localizedTierLabel('unknown', {short:true})],
  ];
  const parts = labels
    .filter(([key]) => counts[key] != null)
    .map(([key, label]) => `${targetIntelCount(counts[key])} ${label}`);
  return parts.length ? parts.join(' · ') : i18nT('log.groupedByProbability', {}, 'People were grouped by model confidence.');
}

function humanizeLogLine(line) {
  const raw = String(line || '').trim();
  const lower = raw.toLowerCase();
  if (!raw) return null;
  let match;
  if ((match = raw.match(/starting query:\s*([^\s]+)/i))) {
    return {key:'start', title:'Analiz başlatıldı', detail:`@${match[1]} için veriler toplanıyor.`, tone:'work', progress:4};
  }
  if ((match = raw.match(/harvest depth.*?:\s*(\d+)/i))) {
    return {key:'depth', title:`Ağ tarama derinliği: ${match[1]}`, detail:'Daha yüksek değer daha fazla hesap kontrol eder ve istek sınırını tetikleyebilir.', tone:'info', progress:7};
  }
  if (/mode:\s*fast/i.test(raw)) {
    return {key:'mode', title:'Hızlı tarama açık', detail:'Yavaş veya sık başarısız olan ek kontroller atlanıyor.', tone:'info', progress:9};
  }
  if (/mode:\s*deep/i.test(raw)) {
    return {key:'mode', title:'Ayrıntılı tarama açık', detail:'Seçilen bütün kontroller çalıştırılıyor.', tone:'info', progress:9};
  }
  if (/target pk yok|otomatik (o|ö)n hazirlik|discovering pk/i.test(raw)) {
    return {key:'profile-prepare', title:'Profil hazırlanıyor', detail:'Instagram profil kimliği bulunuyor.', tone:'work', progress:11};
  }
  if (/cached target pk bulundu|target\s*=.*\(pk=/i.test(raw)) {
    return {key:'profile-found', title:'Profil kaydı bulundu', detail:'Kayıtlı profil kimliğiyle kontroller başlatıldı.', tone:'ok', progress:13};
  }
  if (/failed to discover pk|pk bulunamad/i.test(raw)) {
    return {key:'profile-missing', title:'Profil bulunamadı', detail:'Kullanıcı adı, oturum veya Instagram erişimi kontrol edilmeli.', tone:'err', progress:13};
  }
  if ((match = raw.match(/^\[\*\]\s*Phase\s+(\d+)/i))) {
    const phase = LOG_PHASE_COPY[Number(match[1])];
    if (phase) return {key:`phase-${match[1]}`, ...phase, tone:'work'};
  }
  if (/loaded auth cookies/i.test(raw)) {
    return {key:'session-loaded', title:'Oturum bilgileri yüklendi', detail:'Instagram erişimi şimdi kontrol ediliyor.', tone:'info', progress:14};
  }
  if (/bearer token alındı/i.test(raw)) {
    return {key:'session', title:'Instagram oturumu doğrulandı', detail:'İzin verilen profil kontrolleri çalıştırılıyor.', tone:'ok', progress:16};
  }
  if (/friendship_show:/i.test(raw)) {
    return {key:'relationship', title:'Takip bağlantısı kontrol edildi', detail:'Sonuç, giriş yaptığınız Instagram hesabına göre gösterilir.', tone:'ok', progress:24};
  }
  if ((match = raw.match(/found_non_ui\s*=\s*(\d+)/i))) {
    return {key:'extra-fields', title:`${match[1]} ek profil özelliği bulundu`, detail:'Teknik alanlar sonuç ekranında anlaşılır başlıklarla özetlenecek.', tone:'ok', progress:30};
  }
  if (/\[birthday oracle\]/i.test(raw)) {
    return {key:'birthday', title:'Doğum günü görünürlüğü kontrol edildi', detail:'Bu kontrol kesin doğum tarihi vermez.', tone:'ok', progress:32};
  }
  if ((match = raw.match(/\[avatar\].*?\((\d+(?:\.\d+)?)\s*g[uü]n [oö]nce\)/i))) {
    return {key:'avatar', title:'Profil fotoğrafı zaman bilgisi alındı', detail:`Fotoğraf yaklaşık ${Math.round(Number(match[1]))} gün önce güncellenmiş olabilir.`, tone:'ok', progress:34};
  }
  if (/\[avatar\]/i.test(raw)) {
    return {key:'avatar', title:'Profil fotoğrafı kontrol edildi', detail:'Fotoğrafın teknik zaman ve hesap işaretleri incelendi.', tone:'ok', progress:34};
  }
  if (/story\/highlight activity/i.test(raw)) {
    return {key:'stories', title:'Hikâye ve öne çıkanlar kontrol ediliyor', detail:'Yalnızca bu oturumda erişilebilen bilgiler aranıyor.', tone:'work', progress:36};
  }
  if (/no story\/reel data/i.test(raw)) {
    return {key:'stories-empty', title:'Aktif hikâye bilgisi alınamadı', detail:'Profil gizli olabilir, aktif hikâye olmayabilir veya erişim sınırlı olabilir.', tone:'info', progress:38};
  }
  if (/\[fast\]\s*skipped/i.test(raw)) {
    return {key:'fast-skips', title:'Uzun kontroller atlandı', detail:'Hızlı mod gereksiz beklemeyi azaltıyor.', tone:'info'};
  }
  if (/login-wall|http_error_page/i.test(raw) || /json content extraction skipped/i.test(raw)) {
    return {key:'login-wall', title:'Genel profil sayfası sınırlı yanıt verdi', detail:'Instagram giriş ekranı döndürdü; erişilebilen temel bilgiler korunuyor.', tone:'warn'};
  }
  if ((match = raw.match(/run\s+(\d+)\/(\d+).*union_so_far\s*[=:]\s*(\d+)/i))) {
    return {key:'chain-progress', title:`Bağlantı taraması ${match[1]}/${match[2]}`, detail:`Şimdiye kadar ${targetIntelCount(match[3])} benzersiz hesap bulundu.`, tone:'work', progress:68, update:true};
  }
  if ((match = raw.match(/merged total\s*[=:]\s*(\d+)/i))) {
    return {key:'chain-total', title:`${targetIntelCount(match[1])} bağlantı adayı bulundu`, detail:'Tekrarlanan hesaplar birleştirildi.', tone:'ok', progress:70};
  }
  if ((match = raw.match(/mutual follow\s*[=:]\s*(\d+)/i))) {
    return {key:'mutual-total', title:`${targetIntelCount(match[1])} karşılıklı öneri örtüşmesi`, detail:'Adaylar öneri zincirinin iki yönünde görüldü; bu takip veya arkadaşlık kanıtı değildir.', tone:'ok', progress:85};
  }
  if ((match = raw.match(/target in views\s*:\s*(\d+)/i))) {
    return Number(match[1]) > 0
      ? {key:'share-signal', title:'Paylaşım sıralamasında hedef işareti bulundu', detail:'Sonuç yalnız giriş yaptığınız hesabın öneri sırasına göredir.', tone:'ok', progress:88}
      : {key:'share-signal', title:'Paylaşım sıralamasında hedef görünmedi', detail:'Bu sonuç bağlantı olmadığı anlamına gelmez.', tone:'info', progress:88};
  }
  if (/429|rate.?limit|too many requests/i.test(raw)) {
    return {key:'rate-limit', title:'Instagram geçici istek sınırı uyguladı', detail:'Birkaç dakika bekleyip tekrar deneyebilirsiniz.', tone:'warn'};
  }
  if (/\b401\b|\b403\b|auth.*fail|cookie.*(?:invalid|expired)/i.test(raw)) {
    return {key:'auth-error', title:'Instagram oturumu doğrulanamadı', detail:'Oturum bilgilerini yenileyip yeniden deneyin.', tone:'err'};
  }
  if (/timeout|timed out/i.test(raw)) {
    return {key:'timeout', title:'Instagram zamanında yanıt vermedi', detail:'Analizi bir süre sonra yeniden deneyebilirsiniz.', tone:'warn'};
  }
  if ((match = raw.match(/phase26_29 finished.*returncode=(\d+)/i))) {
    return Number(match[1]) === 0
      ? {key:'collection-done', title:'Veri toplama tamamlandı', detail:'Bulunan hesaplar şimdi kalibre edilmemiş model güveni skorlarıyla değerlendiriliyor.', tone:'ok', progress:90}
      : {key:'collection-failed', title:'Veri toplama tamamlanamadı', detail:'Teknik ayrıntılardan hata nedenini kontrol edebilirsiniz.', tone:'err'};
  }
  if (/relationship_engine done/i.test(raw)) {
    return {key:'scoring-done', title:'Model güveni skorları hesaplandı', detail:'Bulunan kişiler sinyal güçlerine göre gruplandı.', tone:'ok', progress:95};
  }
  if (/tier_counts:/i.test(raw)) {
    try {
      const counts = JSON.parse(raw.slice(raw.indexOf('{')));
      return {key:'scoring-done', title:'Model güveni skorları hesaplandı', detail:formatTierCounts(counts), tierCounts:counts, tone:'ok', progress:95, update:true};
    } catch (_) {
      return null;
    }
  }
  if (/engine skipped/i.test(raw)) {
    return {key:'engine-skipped', title:'Skorlama çalıştırılamadı', detail:'Önceki veri toplama adımı tamamlanmadı.', tone:'warn'};
  }
  if (/complete.*stream closed/i.test(raw)) {
    return {key:'stream-done', title:'Sonuçlar hazırlanıyor', detail:'Yeni veriler ekrana güvenli biçimde yükleniyor.', tone:'work', progress:97};
  }
  if (/reload err/i.test(raw)) {
    return {key:'reload-error', title:'Sonuç ekranı yenilenemedi', detail:'Sayfayı bir kez yenileyerek güncel sonucu açabilirsiniz.', tone:'err'};
  }
  if (/query cancelled|analiz.*iptal/i.test(raw)) {
    return {key:'cancelled', title:'Analiz durduruldu', detail:'Tamamlanmayan sonuçlar ekrana uygulanmadı.', tone:'warn'};
  }
  if (/sse connection lost/i.test(raw)) {
    return {key:'connection-lost', title:'Sunucu bağlantısı kesildi', detail:'Uygulama açıkken analizi yeniden deneyin.', tone:'err'};
  }
  if (/engine error|\[!\].*(?:error|fail)|uncaught|referenceerror/i.test(raw)) {
    return {key:'generic-error', title:'Bir analiz adımı tamamlanamadı', detail:'Ayrıntılı neden teknik kayıtta tutuldu.', tone:'err'};
  }
  return null;
}

function appendLog(text, cls='') {
  appendRawLog(text, cls);
  appendHumanLog(humanizeLogLine(text));
}

function classifyLine(line) {
  const l = line.toLowerCase();
  if (line.startsWith('[*]')) return 'l-info';
  if (line.includes('✓') || line.includes(' OK ')) return 'l-ok';
  if (line.includes('***') || l.includes('found') || l.includes('leak')) return 'l-ok';
  if (l.includes('error') || l.includes('[!]') || l.includes('fail')) return 'l-err';
  if (l.includes('warn') || l.includes('skip') || l.includes('rate')) return 'l-warn';
  return '';
}

function renderLogHeader() {
  const meta = queryState.logMeta;
  if (!meta) return;
  $('#logTitle').textContent = i18nT('log.analysisFor', {username:`@${meta.username}`}, `Analysis for @${meta.username}`);
  $('#logMeta').textContent = i18nT('log.runMeta', {
    mode:i18nT(meta.fastMode ? 'log.fastOn' : 'log.deepOn', {}, meta.fastMode ? 'Fast scan enabled' : 'Detailed scan enabled'),
    sections:meta.sections, depth:meta.depth,
  }, `${meta.fastMode ? 'Fast scan' : 'Detailed scan'} · ${meta.sections} sections · Network depth ${meta.depth}`);
}

function openLogModal(username, phases, fastMode) {
  queryState.logMeta = {
    username:String(username || ''),
    sections:phases.length,
    fastMode:Boolean(fastMode),
    depth:queryState.chainMulti,
  };
  renderLogHeader();
  $('#logStatus').textContent = i18nT('log.preparing', {}, 'Preparing');
  $('#logPre').innerHTML = '';
  $('#logRawPre').innerHTML = '';
  queryState.logKeys = new Set();
  queryState.logEntries = new Map();
  queryState.logHistory = [];
  $('#logProgress').setAttribute('aria-valuenow', '0');
  $('#logProgressBar').style.width = '0%';
  const rawDetails = $('#logRawPre').closest('details');
  if (rawDetails) rawDetails.open = false;
  $('#logCancel').disabled = false;
  setLogProgress(i18nT('log.preparing', {}, 'Preparing'), i18nT('log.preparingSteps', {}, 'Preparing analysis steps.'), 0, 'info');
  $('#logModal').classList.remove('hidden');
  translateUi($('#logModal'));
}

function closeLogModal() {
  $('#logModal').classList.add('hidden');
  if (queryState.evtSource) {
    queryState.runId += 1;
    queryState.evtSource.close();
    queryState.evtSource = null;
  }
}

async function startQuery() {
  const u = $('#newQuery').value.trim();
  if (!u) {
    setStatusKey('status.usernameRequired', {}, 'err', 'A username is required');
    return;
  }
  if (!/^[A-Za-z0-9._]{1,30}$/.test(u)) {
    setStatusKey('status.usernameInvalid', {}, 'err', 'Invalid username');
    return;
  }
  const phases = Array.from(queryState.selectedPhases);
  if (!phases.length) {
    setStatusKey('status.choosePhase', {}, 'err', 'Select at least one analysis section');
    return;
  }
                                             
  const params = new URLSearchParams({username: u});
  if (phases.length && phases.length < PHASE_DEFS.length) {
    params.set('phases', phases.join(','));
  }
  const fastMode = phases.length < PHASE_DEFS.length;
  params.set('fast', fastMode ? '1' : '0');
  params.set('chain_multi', String(queryState.chainMulti));
  params.set('drop_algorithmic', $('#dropAlgo').checked ? '1' : '0');
  if (queryState.evtSource) {
    queryState.evtSource.close();
    queryState.evtSource = null;
  }
  const runId = ++queryState.runId;
  queryState.username = u;
  openLogModal(u, phases, fastMode);
  appendLog(`[*] starting query: ${u}`, 'l-info');
  appendLog(`[*] phases: ${phases.join(',') || 'all'}`, 'l-info');
  appendLog(`[*] harvest depth (chain-multi): ${queryState.chainMulti}`, 'l-info');
  appendLog(`[*] mode: ${fastMode ? 'FAST (dead probes skipped)' : 'DEEP (all probes)'}`, 'l-info');

  const evt = new EventSource('/api/query?' + params.toString());
  queryState.evtSource = evt;
  const isActiveQuery = () => queryState.runId === runId && queryState.evtSource === evt;

  evt.addEventListener('start', e => {
    if (!isActiveQuery()) return;
    const d = JSON.parse(e.data);
    appendLog(i18nT('log.collectorStarted', {},
      'The local collection process started.'), 'l-info');
    setStatusKey('status.analyzing', {username:u}, 'busy', `Analyzing ${u}…`);
  });
  evt.addEventListener('log', e => {
    if (!isActiveQuery()) return;
    const d = JSON.parse(e.data);
    appendLog(d.line, classifyLine(d.line));
  });
  evt.addEventListener('phase_done', e => {
    if (!isActiveQuery()) return;
    const d = JSON.parse(e.data);
    appendLog(`[*] phase26_29 finished — returncode=${d.returncode}`,
              d.returncode === 0 ? 'l-ok' : 'l-err');
  });
  evt.addEventListener('engine_done', e => {
    if (!isActiveQuery()) return;
    const d = JSON.parse(e.data);
    appendLog(`[*] relationship_engine done`, 'l-ok');
    appendLog(`    tier_counts: ${JSON.stringify(d.tier_counts)}`, 'l-ok');
    setStatusKey('status.scoringDone', {}, 'ok', 'Model-confidence scores calculated');
  });
  evt.addEventListener('engine_error', e => {
    if (!isActiveQuery()) return;
    const d = JSON.parse(e.data);
    appendLog(`[!] engine error: ${d.msg}`, 'l-err');
    setStatusKey('status.scoringFailed', {}, 'err', 'Scoring could not be completed');
  });
  evt.addEventListener('engine_skipped', e => {
    if (!isActiveQuery()) return;
    appendLog(`[!] engine SKIPPED (phase26_29 failed)`, 'l-warn');
  });
  evt.addEventListener('error', e => {
    if (!isActiveQuery()) return;
    if (e.data) {
      try {
        const d = JSON.parse(e.data);
        appendLog(`[!] ${d.msg||d.error||'error'}`, 'l-err');
      } catch { appendLog('[!] sse error', 'l-err'); }
    }
  });
  evt.addEventListener('done', async e => {
    if (!isActiveQuery()) return;
    appendLog('[*] complete — stream closed', 'l-info');
    $('#logCancel').disabled = true;
    evt.close();
    if (queryState.evtSource === evt) queryState.evtSource = null;
                                
    try {
      await loadUsers({autoLoad:false, preferredUsername:u});
      if (queryState.runId !== runId) return;
      const sel = $('#userSelect');
                                    
      if ([...sel.options].some(o => o.value === u)) {
        sel.value = u;
        const loaded = await loadUser(u);
        if (queryState.runId !== runId) return;
        if (!loaded && state.pendingUsername !== u) return;
        if (!loaded) throw new Error('result could not be loaded');
        appendHumanLog({key:'ready', title:'Analiz tamamlandı', detail:`@${u} için yeni sonuçlar ekrana yüklendi.`, tone:'ok', progress:100});
      } else {
        throw new Error('queried user not found in result list');
      }
    } catch (err) {
      if (queryState.runId !== runId) return;
      appendLog('[!] reload err: '+err.message, 'l-err');
    }
  });
  evt.onerror = () => {
    if (!isActiveQuery()) return;
    appendLog('[!] SSE connection lost (server closed?)', 'l-err');
    if (queryState.evtSource === evt) {
      evt.close();
      queryState.evtSource = null;
    }
    $('#logCancel').disabled = true;
    setStatusKey('status.serverLost', {}, 'err', 'Server connection lost');
  };
}

function cancelQuery() {
  if (queryState.evtSource) {
    queryState.runId += 1;
    queryState.evtSource.close();
    queryState.evtSource = null;
  }
  appendLog('[!] query cancelled by user (subprocess kill via disconnect)',
            'l-warn');
  $('#logCancel').disabled = true;
  setStatusKey('status.analysisStopped', {}, 'err', 'Analysis stopped');
}

function bindQuery() {
  buildPhaseList();
  $('#queryBtn').addEventListener('click', startQuery);
  $('#newQuery').addEventListener('keydown', e => {
    if (e.key === 'Enter') startQuery();
  });
  $('#phaseBtn').addEventListener('click', e => {
    e.stopPropagation();
    $('#phasePopover').classList.toggle('hidden');
  });
  $('#phaseClose').addEventListener('click', () =>
    $('#phasePopover').classList.add('hidden'));
  $('#phaseAll').addEventListener('click', () => {
    queryState.selectedPhases = new Set(PHASE_DEFS.map(p=>p.key));
    syncPhaseChecks();
  });
  $('#phaseNone').addEventListener('click', () => {
    queryState.selectedPhases.clear();
    syncPhaseChecks();
  });
  $('#phaseFast').addEventListener('click', () => {
    queryState.selectedPhases = new Set(FAST_PHASES);
    syncPhaseChecks();
  });
                                  
  const cm = $('#chainMulti');
  if (cm) {
    cm.addEventListener('change', e => {
      queryState.chainMulti = +e.target.value;
    });
  }
  $('#logClose').addEventListener('click', closeLogModal);
  $('#logCancel').addEventListener('click', cancelQuery);

                                   
  document.addEventListener('click', (e) => {
    const pop = $('#phasePopover');
    if (pop.classList.contains('hidden')) return;
    if (!pop.contains(e.target) && e.target.id !== 'phaseBtn') {
      pop.classList.add('hidden');
    }
  });
}

function refreshForLocaleChange() {
  const select = $('#userSelect');
  const selectedUsername = select ? select.value : (state.pendingUsername || state.username || '');
  const detailWasOpen = Boolean($('#detailPanel') && !$('#detailPanel').classList.contains('hidden'));
  const selectedPerson = state.selectedPk;

  renderUserOptions(state.users, selectedUsername);
  buildPhaseList();
  if (state.data) {
    render();
    if (detailWasOpen && selectedPerson) openDetail(selectedPerson);
  }
  if (queryState.logHistory.length) rerenderHumanLogs();
  renderLogHeader();
  refreshLocalizedStatus();
  translateUi(document);
}

                                                                               
                                                                                 
document.addEventListener('app:localechange', refreshForLocaleChange);

       
bind();
bindQuery();
loadUsers().catch(e => setStatusKey('status.initError', {message:e.message}, 'err', `Initialization error: ${e.message}`));
