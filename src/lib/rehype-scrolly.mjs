/**
 * Two-pane lesson layout, built at compile time.
 *
 * Lessons are written as plain MDX: prose, code fences and <Flow>/<Stack> diagrams in reading
 * order. This plugin turns that into a scrollytelling layout:
 *
 *   <div class="scrolly">
 *     <div class="scrolly-text">   the prose; each visual stays inline (shown on narrow screens)
 *                                  and gets a small marker that points at the stage on wide screens
 *     <aside class="stage">        a sticky pane holding one "frame" per visual (code or diagram)
 *   </div>
 *
 * A small client script (src/components/Stage.astro) swaps the active frame as the reader scrolls
 * past each marker. Without JavaScript the first frame shows and everything stays readable inline.
 * Only lessons and capstone parts (content/lessons/, content/projects/) are transformed.
 */

const DIAGRAMS = new Set(['Flow', 'Stack', 'Trace', 'Compare', 'Bars', 'Lanes', 'Fan', 'States']);

const el = (tagName, properties, children = []) => ({ type: 'element', tagName, properties, children });
const text = (value) => ({ type: 'text', value });

function attr(node, name) {
  const a = (node.attributes || []).find((x) => x.type === 'mdxJsxAttribute' && x.name === name);
  return a && typeof a.value === 'string' ? a.value : undefined;
}

function describe(node) {
  if (node.type === 'mdxJsxFlowElement') {
    const fallback = { Stack: 'Context window', Trace: 'Trace', Compare: 'Comparison', Bars: 'Numbers', Lanes: 'Timeline', Fan: 'Fan-out', States: 'States' };
    return { kind: 'diagram', label: attr(node, 'caption') || fallback[node.name] || 'Diagram' };
  }
  const lang = node.properties?.dataLanguage || 'code';
  return { kind: 'code', label: lang === 'plaintext' || lang === 'txt' ? 'output' : lang };
}

function isVisual(node) {
  if (node.type === 'mdxJsxFlowElement' && DIAGRAMS.has(node.name)) return true;
  return node.type === 'element' && node.tagName === 'pre';
}

export default function rehypeScrolly() {
  return (tree, file) => {
    const path = String(file?.path || file?.history?.[0] || '');
    if (!/content[\\/](lessons|projects)[\\/]/.test(path)) return;

    const keep = [];   // ESM imports/exports must stay at the root
    const body = [];
    for (const n of tree.children) (n.type === 'mdxjsEsm' ? keep : body).push(n);

    const frames = [];
    const textChildren = [];
    let step = -1;
    for (const node of body) {
      if (node.type === 'element' && node.tagName === 'h2') step++;
      if (!isVisual(node)) { textChildren.push(node); continue; }

      const i = frames.length;
      const { kind, label } = describe(node);
      const clone = structuredClone(node);
      // The stage is tall and narrow, so diagrams there are drawn top to bottom.
      if (clone.type === 'mdxJsxFlowElement') clone.attributes = [...(clone.attributes || []), { type: 'mdxJsxAttribute', name: 'vertical', value: null }];
      frames.push(
        el('div', { className: ['frame', `frame-${kind}`], dataFrame: String(i), dataKind: kind, ...(i === 0 ? { dataActive: '' } : {}) }, [
          el('div', { className: ['frame-chrome'] }, [
            el('span', { className: ['dots'], ariaHidden: 'true' }, [el('i', {}), el('i', {}), el('i', {})]),
            el('span', { className: ['frame-label'] }, [text(label)]),
          ]),
          el('div', { className: ['frame-body'] }, [clone]),
        ]),
      );
      textChildren.push(
        el('div', { className: ['vis'], dataFrame: String(i), dataStep: String(Math.max(step, 0)) }, [
          el('button', { type: 'button', className: ['vis-marker'], dataGoto: String(i), ariaLabel: `Show ${kind === 'code' ? 'code' : 'diagram'} on the right: ${label}` }, [
            el('span', { className: ['vis-icon'], ariaHidden: 'true' }, [text(kind === 'code' ? '</>' : '◇')]),
            el('span', { className: ['vis-label'] }, [text(label)]),
            el('span', { className: ['vis-arrow'], ariaHidden: 'true' }, [text('→')]),
          ]),
          el('div', { className: ['vis-inline'] }, [node]),
        ]),
      );
    }
    if (!frames.length) return;

    tree.children = [
      ...keep,
      el('div', { className: ['scrolly'] }, [
        el('div', { className: ['scrolly-text'] }, textChildren),
        el('aside', { className: ['stage'], ariaLabel: 'Code and diagrams for this lesson', dataPagefindIgnore: '' }, [
          el('div', { className: ['stage-inner'] }, [
            el('div', { className: ['stage-head'] }, [
              el('span', { className: ['stage-count'] }, [text(`1 / ${frames.length}`)]),
              el('span', { className: ['stage-pips'], ariaHidden: 'true' }, frames.map((_, i) => el('i', { dataPip: String(i), ...(i === 0 ? { dataOn: '' } : {}) }))),
              el('span', { className: ['stage-nav'] }, [
                el('button', { type: 'button', className: ['icon-btn'], dataStagePrev: '', ariaLabel: 'Previous figure' }, [text('↑')]),
                el('button', { type: 'button', className: ['icon-btn'], dataStageNext: '', ariaLabel: 'Next figure' }, [text('↓')]),
              ]),
            ]),
            el('div', { className: ['stage-frames'] }, frames),
          ]),
        ]),
      ]),
    ];
  };
}
