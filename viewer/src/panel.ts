import { h } from "./dom";
import { renderEditor, type EditorHost } from "./editor";
import { REASON_LABELS, reviewReasons } from "./review";
import type { Box, Device, Point3, Tag } from "./types";

export interface PanelHost extends EditorHost {
  currentSweep(): string | null;
  showBox(box: Box): void;
  openTag(tag: Tag): void;
  openDevice(tag: Tag, device: Device): void;
  close(): void;
}

const KIND_LABELS: Record<string, string> = {
  manual: "Manual",
  drawing: "Drawing",
  maintenance_report: "Maintenance report",
  inspection_report: "Inspection report",
};

const fmtPoint = (p: Point3 | null) => (p ? `${p.x.toFixed(2)}, ${p.y.toFixed(2)}, ${p.z.toFixed(2)}` : "None");
const row = (label: string, value: Node | string) => [h("dt", {}, label), h("dd", {}, value)];

export const deviceLabel = (d: Device) => d.name || `Unnamed ${d.device_type}`;

export class Panel {
  selection: { tag: Tag; device?: Device } | null = null;
  editing = false;

  constructor(readonly root: HTMLElement, private readonly host: PanelHost) {}

  show(tag: Tag, device?: Device) {
    if (this.selection?.tag.id !== tag.id || this.selection.device?.device_id !== device?.device_id) this.editing = false;
    this.selection = { tag, device };
    this.render();
    this.root.hidden = false;
    this.root.querySelector<HTMLElement>("h2")?.focus();
  }

  hide() {
    this.selection = null;
    this.editing = false;
    this.root.hidden = true;
    this.root.replaceChildren();
  }

  render() {
    if (!this.selection) return;
    const { tag, device } = this.selection;
    const close = h("button", { type: "button", class: "close", "aria-label": "Close details", onclick: () => this.host.close() }, "×");
    const body = device ? this.deviceBody(tag, device) : this.tagBody(tag);
    this.root.replaceChildren(h("div", { class: "panel-head" }, body.title, close), ...body.content);
  }

  private tagBody(tag: Tag) {
    const t = this.host.threshold();
    return {
      title: h("h2", { id: "panel-title", tabIndex: -1 }, tag.cabinet),
      content: [
        h("p", { class: "kind" }, "Cabinet tag"),
        h("dl", { class: "facts" }, row("Tag ID", tag.id), row("Path", tag.path.join(" / ")), row("Anchor", fmtPoint(tag.anchor))),
        h("h3", {}, `Devices (${tag.devices.length})`),
        tag.devices.length
          ? h(
              "ul",
              { class: "device-list" },
              tag.devices.map((d) => {
                const review = reviewReasons(d, t).length > 0;
                return h(
                  "li",
                  {},
                  h(
                    "button",
                    { type: "button", class: `link ${review ? "review" : "ok"}`, onclick: () => this.host.openDevice(tag, d) },
                    h("span", { class: "badge", "aria-hidden": "true" }, review ? "!" : "✓"),
                    `${deviceLabel(d)} (${review ? "review" : "OK"})`,
                  ),
                );
              }),
            )
          : h("p", {}, "No devices in this cabinet."),
      ],
    };
  }

  private deviceBody(tag: Tag, d: Device) {
    const reasons = reviewReasons(d, this.host.threshold());
    const sweep = this.host.currentSweep();
    const content: Node[] = [
      h("p", { class: "kind" }, `${d.device_type} device`),
      h(
        "dl",
        { class: "facts" },
        row("Cabinet", h("button", { type: "button", class: "link", onclick: () => this.host.openTag(tag) }, tag.cabinet)),
        row("Name", d.name || "None (OCR read no text)"),
        row("Device type", d.device_type),
        row("Confidence", d.confidence.toFixed(3)),
        row("Review", reasons.length ? "Yes" : "No"),
        row("Anchor", fmtPoint(d.anchor)),
        row("Device ID", d.device_id),
      ),
    ];
    if (reasons.length) {
      content.push(h("h3", {}, "Review reasons"), h("ul", { class: "reasons" }, reasons.map((r) => h("li", {}, REASON_LABELS[r] ?? r))));
    }
    content.push(
      h("h3", {}, `Boxes (${d.boxes.length})`),
      d.boxes.length
        ? h(
            "ul",
            { class: "boxes" },
            d.boxes.map((b) =>
              h(
                "li",
                { class: b.scan_position === sweep ? "current" : "" },
                h(
                  "span",
                  {},
                  `${b.scan_position}: ${Math.round(b.width)} x ${Math.round(b.height)} px at ${Math.round(b.x)}, ${Math.round(b.y)}`,
                  b.confidence !== undefined ? `, confidence ${b.confidence.toFixed(3)}` : "",
                  b.scan_position === sweep ? " (outlined)" : "",
                ),
                h("button", { type: "button", onclick: () => this.host.showBox(b), "aria-label": `Show the box in ${b.scan_position}` }, "Show"),
              ),
            ),
          )
        : h("p", {}, "No boxes."),
      h("h3", {}, "Documents"),
      d.documents.length
        ? h(
            "ul",
            { class: "docs" },
            d.documents.map((doc) =>
              h(
                "li",
                {},
                h("a", { href: doc.url, target: "_blank", rel: "noopener" }, doc.title, h("span", { class: "sr-only" }, " (opens in a new tab)")),
                h("span", { class: "doc-kind" }, KIND_LABELS[doc.kind] ?? doc.kind),
              ),
            ),
          )
        : h("p", {}, "No documents."),
    );
    if (this.editing) {
      content.push(
        renderEditor(
          {
            ...this.host,
            cancel: () => {
              this.editing = false;
              this.render();
            },
          },
          tag,
          d,
        ),
      );
    } else if (reasons.length) {
      content.push(
        h(
          "button",
          {
            type: "button",
            class: "primary",
            onclick: () => {
              this.editing = true;
              this.render();
              this.root.querySelector<HTMLElement>("#edit-name")?.focus();
            },
          },
          "Edit device",
        ),
      );
    }
    return { title: h("h2", { id: "panel-title", tabIndex: -1 }, deviceLabel(d)), content };
  }
}
