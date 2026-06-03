// ============================================================
// N8N CODE NODE: Дни рождения + Праздники (РФ + Латвия + Беларусь)
// Birthday & Holiday Notification Bot v4
// ============================================================
// Таблица Google Sheets (колонки):
//   Имя | Отдел | Руководитель | Пол | День рождения | Страна | ID чата отдела | Доп группы
//
// День рождения: формат DD.MM  (текст, напр. 14.10 — НЕ число!)
// Пол: Male / Female
// ID чата отдела: Chat ID Telegram-группы отдела
// Доп группы: Chat ID через запятую (межотдельные поздравления)
//
// v4: добавлены недостающие официальные праздники Латвии
//     (Страстная пятница, 2-й день Пасхи, Сочельник, 2-й день
//      Рождества, канун Нового года).
// ============================================================

// ─── НАСТРОЙКИ ───────────────────────────────────────────────

// Чат руководства — получает ВСЕ оповещения
// ⚠️ ТЕСТ: сейчас стоит тестовый ID. Перед продакшеном заменить
//          на реальный Chat ID чата руководства.
const MANAGEMENT_CHAT = '6091784070';

// За сколько дней до ДР напоминать
const BIRTHDAY_REMIND_DAYS = [7, 2, 0];

// ─── ПРАЗДНИКИ РФ + ЛАТВИЯ + БЕЛАРУСЬ ───────────────────────
// remind_days — за сколько дней напоминать
// gender: 'Male' / 'Female' / 'all'
// msg21/msg14/msg7/msg2/msgDay — кастомные сообщения (null = стандартное)

const HOLIDAYS = [

  // ══════════════════════════════════════════════
  // ОБЩИЕ ПРАЗДНИКИ
  // ══════════════════════════════════════════════

  // 🎄 Новый год — РФ + Латвия + Беларусь
  {
    date: '01.01', name: 'Новый год', icon: '🎄', gender: 'all',
    remind_days: [21, 14, 7, 0],
    msg21: '🎄 Через три недели — Новый год!\nСамое время начать думать о подарках и планах! 🎁',
    msg14: '🎄 Через две недели — Новый год!\nПора начинать подготовку к празднику! 🎁',
    msg7: '🎄 Через неделю — Новый год!\nФинальная неделя — подарки, поздравления, планы! 🎅',
    msgDay: '🎄 Хо-хо-хо! С Новым годом! 🎉\nПусть новый год принесёт удачу, новые победы и классную команду!\nС праздником, коллеги! 🥂',
  },

  // ⛪ Рождество православное (7 янв) — РФ + Беларусь
  {
    date: '07.01', name: 'Рождество Христово (РФ, Беларусь)', icon: '⛪', gender: 'all',
    remind_days: [2, 0],
    msgDay: '⛪ С Рождеством Христовым!\nСветлого праздника, коллеги! 🙏',
  },

  // 🎖️ 23 февраля — РФ + Беларусь
  {
    date: '23.02', name: 'День защитника Отечества (РФ, Беларусь)', icon: '🎖️', gender: 'Male',
    remind_days: [7, 2, 0],
    msg7: '🎖️ Через неделю — 23 Февраля!\nНе забудьте подготовить поздравления для наших мужчин! 🎁',
    msg2: '🎖️ Послезавтра — День защитника Отечества!\nПодготовьте поздравления! 💪',
    msgDay: '🎖️ Дорогие мужчины, с праздником!\nСилы, мужества и уверенности!\nС 23 Февраля! 💪',
  },

  // 💐 8 Марта — РФ + Латвия + Беларусь
  {
    date: '08.03', name: 'Международный женский день', icon: '💐', gender: 'Female',
    remind_days: [7, 2, 0],
    msg7: '💐 Через неделю — 8 Марта!\nНе забудьте подготовить поздравления для наших девушек! 🎁',
    msg2: '💐 Послезавтра — 8 Марта!\nПоследний шанс подготовить поздравления! 🌸',
    msgDay: '💐 Дорогие девушки, с праздником!\nКрасоты, вдохновения и радости! 🌷\nС 8 Марта! 💕',
  },

  // 🌿 1 Мая — РФ + Латвия + Беларусь
  {
    date: '01.05', name: 'Праздник Весны и Труда', icon: '🌿', gender: 'all',
    remind_days: [2, 0],
    msgDay: '🌿 С Праздником Весны и Труда!\nОтличного настроения и тёплых майских дней!\nС праздником, коллеги! ☀️',
  },

  // 🎖️ 9 Мая — РФ + Беларусь
  {
    date: '09.05', name: 'День Победы (РФ, Беларусь)', icon: '🎖️', gender: 'all',
    remind_days: [2, 0],
    msgDay: '🎖️ Сегодня — День Победы!\nПомним. Гордимся. С праздником, коллеги! 🕯️',
  },

  // 🎄 Рождество католическое (25 дек) — Латвия + Беларусь
  {
    date: '25.12', name: 'Рождество Христово (Латвия, Беларусь)', icon: '🎄', gender: 'all',
    remind_days: [2, 0],
    msgDay: '🎄 С Рождеством Христовым!\nТёплого и светлого праздника! ✨',
  },

  // ══════════════════════════════════════════════
  // РОССИЯ (уникальные)
  // ══════════════════════════════════════════════

  // 🇷🇺 День России
  {
    date: '12.06', name: 'День России', icon: '🇷🇺', gender: 'all',
    remind_days: [2, 0],
    msgDay: '🇷🇺 Сегодня — День России!\nС праздником, коллеги! 🎉',
  },

  // 🇷🇺 День народного единства
  {
    date: '04.11', name: 'День народного единства', icon: '🇷🇺', gender: 'all',
    remind_days: [2, 0], msgDay: null,
  },

  // ══════════════════════════════════════════════
  // ЛАТВИЯ (уникальные)
  // ══════════════════════════════════════════════

  // ✝️ Страстная пятница (Lielā Piektdiena) — дата 2026, ОБНОВЛЯТЬ ЕЖЕГОДНО
  {
    date: '03.04', name: 'Страстная пятница (Латвия)', icon: '✝️', gender: 'all',
    remind_days: [0],
    msgDay: '✝️ Сегодня — Страстная пятница.\nТихого и светлого дня, коллеги. 🙏',
  },

  // 🥚 Пасха (Lieldienas) — дата 2026, ОБНОВЛЯТЬ ЕЖЕГОДНО
  {
    date: '05.04', name: 'Пасха (Латвия)', icon: '🥚', gender: 'all',
    remind_days: [2, 0],
    msgDay: '🥚 Светлой Пасхи!\nС праздником, коллеги! 🙏',
  },

  // 🐣 Второй день Пасхи (Otrās Lieldienas) — дата 2026, ОБНОВЛЯТЬ ЕЖЕГОДНО
  {
    date: '06.04', name: 'Второй день Пасхи (Латвия)', icon: '🐣', gender: 'all',
    remind_days: [0],
    msgDay: '🐣 Второй день Пасхи!\nСветлых праздничных дней, коллеги! 🌷',
  },

  // 🇱🇻 День восстановления независимости Латвии
  {
    date: '04.05', name: 'День восстановления независимости Латвии', icon: '🇱🇻', gender: 'all',
    remind_days: [2, 0],
    msgDay: '🇱🇻 Сегодня — День восстановления независимости Латвии!\nС праздником! 🎉',
  },

  // 👩 День матери (Латвия, 2-е воскресенье мая) — дата 2026, ОБНОВЛЯТЬ ЕЖЕГОДНО
  {
    date: '10.05', name: 'День матери (Латвия)', icon: '👩', gender: 'all',
    remind_days: [2, 0],
    msgDay: '👩 Сегодня — День матери!\nВсем мамам — тепла, любви и благодарности! 💐\nС праздником! 💕',
  },

  // 🔥 Лиго
  {
    date: '23.06', name: 'Лиго (Латвия)', icon: '🔥', gender: 'all',
    remind_days: [2, 0],
    msgDay: '🔥 Сегодня — Лиго!\nС праздником, коллеги! 🌿🎉',
  },

  // 🌅 Янов день
  {
    date: '24.06', name: 'Янов день (Латвия)', icon: '🌅', gender: 'all',
    remind_days: [0],
    msgDay: '🌅 Сегодня — Янов день!\nС праздником! ☀️',
  },

  // 🇱🇻 День провозглашения Латвийской Республики
  {
    date: '18.11', name: 'День провозглашения Латвийской Республики', icon: '🇱🇻', gender: 'all',
    remind_days: [2, 0],
    msgDay: '🇱🇻 Сегодня — День провозглашения Латвийской Республики!\nС праздником! 🎉',
  },

  // 🎄 Сочельник / канун Рождества (Латвия)
  {
    date: '24.12', name: 'Сочельник (Латвия)', icon: '🎄', gender: 'all',
    remind_days: [0],
    msgDay: '🎄 Сегодня — Сочельник, канун Рождества!\nУютного и тёплого вечера, коллеги! ✨',
  },

  // 🎄 Второй день Рождества (Латвия)
  {
    date: '26.12', name: 'Второй день Рождества (Латвия)', icon: '🎄', gender: 'all',
    remind_days: [0],
    msgDay: '🎄 Второй день Рождества!\nПродолжаем праздновать, коллеги! ✨',
  },

  // 🎆 Канун Нового года (Латвия)
  {
    date: '31.12', name: 'Канун Нового года (Латвия)', icon: '🎆', gender: 'all',
    remind_days: [0],
    msgDay: '🎆 Сегодня — канун Нового года!\nС наступающим, коллеги! Пусть всё задуманное сбудется! 🥂',
  },

  // ══════════════════════════════════════════════
  // БЕЛАРУСЬ (уникальные)
  // ══════════════════════════════════════════════

  // 🕯️ Радуница — дата 2026, ОБНОВЛЯТЬ ЕЖЕГОДНО
  {
    date: '21.04', name: 'Радуница (Беларусь)', icon: '🕯️', gender: 'all',
    remind_days: [2, 0], msgDay: null,
  },

  // 🇧🇾 День Независимости Беларуси
  {
    date: '03.07', name: 'День Независимости Беларуси', icon: '🇧🇾', gender: 'all',
    remind_days: [2, 0],
    msgDay: '🇧🇾 Сегодня — День Независимости Беларуси!\nС праздником! 🎉',
  },

  // 📜 День Октябрьской революции
  {
    date: '07.11', name: 'День Октябрьской революции (Беларусь)', icon: '📜', gender: 'all',
    remind_days: [0], msgDay: null,
  },
];

// ─── ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ─────────────────────────────────

function getDiffDays(targetDay, targetMonth) {
  const today = new Date();
  const todayNorm = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const target = new Date(today.getFullYear(), targetMonth - 1, targetDay);
  const diffTime = target.getTime() - todayNorm.getTime();
  return Math.round(diffTime / (1000 * 60 * 60 * 24));
}

function parseDDMM(str) {
  if (!str && str !== 0) return null;
  const clean = String(str).trim();
  if (!clean.includes('.')) return null;
  const [day, month] = clean.split('.').map(Number);
  if (!day || !month || day < 1 || day > 31 || month < 1 || month > 12) return null;
  return { day, month };
}

function addResult(results, message, chatId) {
  if (message && chatId) {
    results.push({ json: { message, chatId: Number(String(chatId).trim()) } });
  }
}

// ─── ОСНОВНАЯ ЛОГИКА ─────────────────────────────────────────

const results = [];

// ═══════════════════════════════════════════════════════════════
// БЛОК 1: ДНИ РОЖДЕНИЯ
// ═══════════════════════════════════════════════════════════════

for (const item of $input.all()) {
  const name = item.json['Имя'] || '';
  const department = item.json['Отдел'] || '';
  const teamLead = item.json['Руководитель'] || '';
  const gender = item.json['Пол'] || '';
  const birthdayRaw = item.json['День рождения'] || '';
  const country = item.json['Страна'] || '';
  const deptChatId = item.json['ID чата отдела'] || '';
  const extraGroups = item.json['Доп группы'] || '';

  if (!name || !birthdayRaw) continue;

  const bd = parseDDMM(birthdayRaw);
  if (!bd) continue;

  const diffDays = getDiffDays(bd.day, bd.month);

  if (!BIRTHDAY_REMIND_DAYS.includes(diffDays)) continue;

  let msgShort = '';
  let msgFull = '';

  if (diffDays === 7) {
    msgShort = `📅 Через неделю день рождения!\n👤 ${name}\n`;
    if (department) msgShort += `🏢 ${department}\n`;
    if (teamLead) msgShort += `📌 Ответственный: ${teamLead}\n`;
    msgShort += `\nПодготовь поздравление!`;

    msgFull = `📅 Через неделю день рождения!\n👤 ${name}\n`;
    if (department) msgFull += `🏢 ${department}\n`;
    if (country) msgFull += `🌍 ${country}\n`;
    if (teamLead) msgFull += `📌 Ответственный: ${teamLead}\n`;
    msgFull += `\nПодготовь поздравление!`;
  }

  if (diffDays === 2) {
    msgShort = `⏰ Послезавтра день рождения!\n👤 ${name}\n`;
    if (department) msgShort += `🏢 ${department}\n`;
    if (teamLead) msgShort += `📌 Ответственный: ${teamLead}\n`;
    msgShort += `\nНе забудь поздравить!`;

    msgFull = `⏰ Послезавтра день рождения!\n👤 ${name}\n`;
    if (department) msgFull += `🏢 ${department}\n`;
    if (country) msgFull += `🌍 ${country}\n`;
    if (teamLead) msgFull += `📌 Ответственный: ${teamLead}\n`;
    msgFull += `\nНе забудь поздравить!`;
  }

  if (diffDays === 0) {
    msgShort = `🎂 Сегодня день рождения!\n👤 ${name}\n`;
    if (department) msgShort += `🏢 ${department}\n`;
    if (teamLead) msgShort += `📌 Ответственный: ${teamLead}\n`;
    msgShort += `\nПоздравляй! 🎉`;

    msgFull = `🎂 Сегодня день рождения!\n👤 ${name}\n`;
    if (department) msgFull += `🏢 ${department}\n`;
    if (country) msgFull += `🌍 ${country}\n`;
    if (teamLead) msgFull += `📌 Ответственный: ${teamLead}\n`;
    msgFull += `\nПоздравляй! 🎉`;
  }

  if (!msgShort) continue;

  if (deptChatId) {
    addResult(results, msgShort, deptChatId);
  }

  if (extraGroups) {
    const extras = String(extraGroups).split(',');
    for (const extra of extras) {
      const trimmed = extra.trim();
      if (trimmed) {
        addResult(results, msgShort, trimmed);
      }
    }
  }

  addResult(results, msgFull, MANAGEMENT_CHAT);
}

// ═══════════════════════════════════════════════════════════════
// БЛОК 2: ПРАЗДНИКИ (РФ + Латвия + Беларусь)
// ═══════════════════════════════════════════════════════════════

for (const holiday of HOLIDAYS) {
  const hd = parseDDMM(holiday.date);
  if (!hd) continue;

  const diffDays = getDiffDays(hd.day, hd.month);

  if (!holiday.remind_days.includes(diffDays)) continue;

  const allDeptChats = new Set();
  const allExtraChats = new Set();
  const namesByDeptChat = {};
  const namesByExtra = {};
  const allNames = [];
  const allNamesWithCountry = [];

  for (const item of $input.all()) {
    const name = item.json['Имя'] || '';
    const gender = item.json['Пол'] || '';
    const country = item.json['Страна'] || '';
    const deptChatId = item.json['ID чата отдела'] || '';
    const extraGroups = item.json['Доп группы'] || '';

    if (!name) continue;

    if (holiday.gender !== 'all' && gender !== holiday.gender) continue;

    allNames.push(name);
    allNamesWithCountry.push(country ? `${name} (${country})` : name);

    if (deptChatId) {
      const key = String(deptChatId).trim();
      allDeptChats.add(key);
      if (!namesByDeptChat[key]) namesByDeptChat[key] = [];
      namesByDeptChat[key].push(name);
    }

    if (extraGroups) {
      const extras = String(extraGroups).split(',');
      for (const extra of extras) {
        const trimmed = extra.trim();
        if (trimmed) {
          allExtraChats.add(trimmed);
          if (!namesByExtra[trimmed]) namesByExtra[trimmed] = [];
          namesByExtra[trimmed].push(name);
        }
      }
    }
  }

  // Определяем кастомное сообщение
  let customMsg = null;
  if (diffDays === 0 && holiday.msgDay) {
    customMsg = holiday.msgDay;
  } else if (diffDays === 2 && holiday.msg2) {
    customMsg = holiday.msg2;
  } else if (diffDays === 7 && holiday.msg7) {
    customMsg = holiday.msg7;
  } else if (diffDays === 14 && holiday.msg14) {
    customMsg = holiday.msg14;
  } else if (diffDays === 21 && holiday.msg21) {
    customMsg = holiday.msg21;
  }

  // ── Гендерные праздники (8 марта, 23 февраля) ──
  if (holiday.gender !== 'all') {

    if (allNames.length === 0) continue;

    if (diffDays === 0 && customMsg) {
      for (const [chatId, names] of Object.entries(namesByDeptChat)) {
        const nameList = names.map(n => `  • ${n}`).join('\n');
        addResult(results, `${customMsg}\n\nПоздравляем:\n${nameList}`, chatId);
      }
      for (const [chatId, names] of Object.entries(namesByExtra)) {
        const nameList = names.map(n => `  • ${n}`).join('\n');
        addResult(results, `${customMsg}\n\nПоздравляем:\n${nameList}`, chatId);
      }
      const fullList = allNamesWithCountry.map(n => `  • ${n}`).join('\n');
      addResult(results, `${customMsg}\n\n👥 Поздравляем (${allNames.length} чел.):\n${fullList}`, MANAGEMENT_CHAT);

    } else {
      const prefix = customMsg || (diffDays >= 7
        ? `📅 Через ${diffDays === 21 ? 'три недели' : diffDays === 14 ? 'две недели' : 'неделю'} — ${holiday.icon} ${holiday.name}!`
        : `⏰ Послезавтра — ${holiday.icon} ${holiday.name}!`);

      for (const [chatId, names] of Object.entries(namesByDeptChat)) {
        const nameList = names.map(n => `  • ${n}`).join('\n');
        addResult(results, `${prefix}\n\nПоздравляем:\n${nameList}\n\nПодготовьте поздравления! 🎁`, chatId);
      }
      for (const [chatId, names] of Object.entries(namesByExtra)) {
        const nameList = names.map(n => `  • ${n}`).join('\n');
        addResult(results, `${prefix}\n\nПоздравляем:\n${nameList}\n\nПодготовьте поздравления! 🎁`, chatId);
      }
      const fullList = allNamesWithCountry.map(n => `  • ${n}`).join('\n');
      addResult(results, `${prefix}\n\n👥 Поздравляем (${allNames.length} чел.):\n${fullList}\n\nПодготовьте поздравления! 🎁`, MANAGEMENT_CHAT);
    }

  // ── Общие праздники ──
  } else {

    if (diffDays === 0) {
      const msg = customMsg || `${holiday.icon} Сегодня — ${holiday.name}!\nС праздником, коллеги! 🎉`;
      for (const chatId of allDeptChats) addResult(results, msg, chatId);
      for (const chatId of allExtraChats) addResult(results, msg, chatId);
      addResult(results, msg, MANAGEMENT_CHAT);

    } else {
      const msg = customMsg || (diffDays >= 7
        ? `📅 Через ${diffDays === 21 ? 'три недели' : diffDays === 14 ? 'две недели' : 'неделю'} — ${holiday.icon} ${holiday.name}!`
        : `⏰ Послезавтра — ${holiday.icon} ${holiday.name}!`);
      for (const chatId of allDeptChats) addResult(results, msg, chatId);
      for (const chatId of allExtraChats) addResult(results, msg, chatId);
      addResult(results, msg, MANAGEMENT_CHAT);
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// ВОЗВРАТ РЕЗУЛЬТАТОВ
// ═══════════════════════════════════════════════════════════════

return results.length > 0
  ? results
  : [{ json: { message: null, chatId: null } }];
