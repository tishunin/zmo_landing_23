const DESIGN_WIDTH = 850;
const DESIGN_HEIGHT = 6926;
const MODAL_WIDTH = 482;
const MODAL_HEIGHT = 674;

const root = document.querySelector('#landing-root');
const shell = document.querySelector('.landing-shell');
const dialog = document.querySelector('#registration-dialog');
const form = document.querySelector('#registration-form');
const success = document.querySelector('.registration__success');
const successClose = document.querySelector('[data-close-dialog]');
const dialogClose = document.querySelector('.registration__close');

function updateScale() {
  const scale = Math.min(document.documentElement.clientWidth / DESIGN_WIDTH, 1);
  document.documentElement.style.setProperty('--landing-scale', String(scale));
  shell.style.height = `${DESIGN_HEIGHT * scale}px`;
}

function updateModalScale() {
  const scale = Math.min(
    (window.innerWidth - 16) / MODAL_WIDTH,
    (window.innerHeight - 16) / MODAL_HEIGHT,
    1,
  );
  document.documentElement.style.setProperty('--modal-scale', String(scale));
}

function openRegistration() {
  form.hidden = false;
  success.hidden = true;
  updateModalScale();
  dialog.showModal();
  requestAnimationFrame(() => form.elements.name.focus({ preventScroll: true }));
}

function closeRegistration() {
  dialog.close();
}

function initializeLanding() {
  const villageLinks = {
    '13:305': ['https://kpgreenwood.ru', 'Greenwood'],
    '13:307': ['https://kp-greenpark.ru', 'Green Park'],
    '13:303': ['https://beketovopark.ru', 'Бекетово Park'],
    '13:301': ['https://kpgreenforest.ru', 'Green Forest'],
    '13:299': ['https://kpshelkovo.ru', 'Shelkovo Eco Club'],
    '13:295': ['https://kp-panoramariver.ru', 'Panorama River'],
    '13:297': ['https://kp-whitepark.ru', 'White Park'],
    '13:293': ['https://kp-river.ru', 'River Park'],
    '13:292': ['https://kp-greenriver.ru', 'Green River'],
  };

  Object.entries(villageLinks).forEach(([nodeId, [url, name]]) => {
    const text = root.querySelector(`[data-node-id="${nodeId}"]`);
    if (!text) return;

    const link = document.createElement('a');
    [...text.attributes].forEach(({ name: attribute, value }) => link.setAttribute(attribute, value));
    link.classList.add('village-link');
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.setAttribute('aria-label', `${name} — открыть сайт`);
    link.textContent = text.textContent;
    text.replaceWith(link);
  });

  const socialLinks = {
    '13:453': ['https://t.me/zemlya_m_o', 'Telegram', 'social-telegram-link'],
    '13:443': ['https://vk.com/zemlya_m_o', 'ВКонтакте', 'social-vk-link'],
    '13:450': ['http://www.youtube.com/@zemlya_m_o', 'YouTube', 'social-youtube-link'],
    '13:444': ['https://rutube.ru/channel/42205794/', 'Rutube', 'social-rutube-link'],
    '13:434': ['https://dzen.ru/zemlya_m_o', 'Дзен', 'social-dzen-link'],
  };

  Object.entries(socialLinks).forEach(([nodeId, [url, name, id]]) => {
    const icon = root.querySelector(`[data-node-id="${nodeId}"]`);
    if (!icon) return;

    const link = document.createElement('a');
    [...icon.attributes].forEach(({ name: attribute, value }) => link.setAttribute(attribute, value));
    link.id = id;
    link.classList.add('social-link');
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.setAttribute('aria-label', `${name} — открыть страницу`);
    link.append(...icon.childNodes);
    icon.replaceWith(link);
  });

  const recapLink = document.createElement('a');
  recapLink.id = 'last-year-video-link';
  recapLink.className = 'last-year-video-link';
  recapLink.href = 'https://rutube.ru/video/962444b8a8b9953d12e2d2734bbdbb24/';
  recapLink.target = '_blank';
  recapLink.rel = 'noopener noreferrer';
  recapLink.setAttribute('aria-label', 'Посмотреть, как это было в прошлом году, на Rutube');
  root.querySelector('.figma-canvas').append(recapLink);

  const trigger = document.createElement('button');
  trigger.id = 'registration-trigger';
  trigger.className = 'registration-hotspot';
  trigger.type = 'button';
  trigger.textContent = 'Регистрация';
  trigger.setAttribute('aria-haspopup', 'dialog');
  trigger.setAttribute('aria-controls', 'registration-dialog');
  trigger.addEventListener('click', openRegistration);
  root.querySelector('.figma-canvas').append(trigger);

  assignUniqueIds();
}

function assignUniqueIds() {
  document.querySelectorAll('[data-node-id]').forEach((element) => {
    if (element.id) return;
    element.id = `figma-${element.dataset.nodeId.replaceAll(':', '-')}`;
  });

  let sequence = 1;
  document.querySelectorAll('body *:not([id])').forEach((element) => {
    let id;
    do {
      id = `ui-${element.tagName.toLowerCase()}-${String(sequence).padStart(3, '0')}`;
      sequence += 1;
    } while (document.getElementById(id));
    element.id = id;
  });
}

dialog.addEventListener('click', (event) => {
  const bounds = dialog.getBoundingClientRect();
  const outside = event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom;
  if (outside) closeRegistration();
});

form.addEventListener('submit', (event) => {
  event.preventDefault();
  if (!form.reportValidity()) return;
  form.hidden = true;
  success.hidden = false;
  successClose.focus();
  form.reset();
});

successClose.addEventListener('click', closeRegistration);
dialogClose.addEventListener('click', closeRegistration);
window.addEventListener('resize', () => { updateScale(); if (dialog.open) updateModalScale(); });

updateScale();
initializeLanding();
