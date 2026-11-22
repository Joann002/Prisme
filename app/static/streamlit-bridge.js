const bridges = new WeakMap();
let serial = 0;

export default function setup(component) {
  const root = component.parentElement.querySelector("[data-prisme]");
  if (!root) return;
  let bridge = bridges.get(root);
  if (!bridge) {
    bridge = {pending: new Map(), send: component.setTriggerValue, queue: [], active: null};
    bridge.next = () => {
      if (!bridge.active && bridge.queue.length) {
        bridge.active = bridge.queue.shift();
        bridge.send("command", bridge.active);
      }
    };
    const request = (action, payload) => new Promise((resolve, reject) => {
      const id = ++serial;
      const timer = setTimeout(() => {
        if (!bridge.pending.delete(id)) return;
        bridge.queue = bridge.queue.filter((operation) => operation.id !== id);
        if (bridge.active?.id === id) bridge.active = null;
        reject(new Error("Le serveur a mis trop de temps à répondre."));
        bridge.next();
      }, 20000);
      bridge.pending.set(id, {resolve, reject, timer});
      bridge.queue.push({id, action, payload});
      bridge.next();
    });
    bridges.set(root, bridge);
    mount(root, component.data.assets, request, component.data.metadata);
  }
  bridge.send = component.setTriggerValue;
  const result = component.data.response;
  if (result && bridge.pending.has(result.id)) {
    const pending = bridge.pending.get(result.id);
    clearTimeout(pending.timer);
    bridge.pending.delete(result.id);
    if (bridge.active?.id === result.id) bridge.active = null;
    if (result.error) pending.reject(new Error(result.error));
    else pending.resolve(result.value);
    bridge.next();
  }
}
