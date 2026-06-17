using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// A layout group that wraps children onto new lines
/// when they exceed the container width (or height).
/// Drop this onto any RectTransform that has child UI elements.
/// </summary>
[AddComponentMenu("Layout/Wrap Layout Group")]
public class WrapLayoutGroup : LayoutGroup {
    // ── Enums ──────────────────────────────────────────────────────
    public enum Axis { Horizontal = 0, Vertical = 1 }

    // ── Serialized fields ──────────────────────────────────────────
    [SerializeField] protected Axis m_StartAxis = Axis.Horizontal;
    [SerializeField] protected Vector2 m_Spacing = Vector2.zero;
    [SerializeField] protected bool m_ChildForceExpandWidth = false;
    [SerializeField] protected bool m_ChildForceExpandHeight = false;
    [SerializeField] protected bool m_ChildControlWidth = false;
    [SerializeField] protected bool m_ChildControlHeight = false;
    [SerializeField] protected bool m_ChildScaleWidth = false;
    [SerializeField] protected bool m_ChildScaleHeight = false;

    // ── Public accessors ───────────────────────────────────────────
    public Axis startAxis { get => m_StartAxis; set => SetProperty(ref m_StartAxis, value); }
    public Vector2 spacing { get => m_Spacing; set => SetProperty(ref m_Spacing, value); }
    public bool childForceExpandWidth { get => m_ChildForceExpandWidth; set => SetProperty(ref m_ChildForceExpandWidth, value); }
    public bool childForceExpandHeight { get => m_ChildForceExpandHeight; set => SetProperty(ref m_ChildForceExpandHeight, value); }
    public bool childControlWidth { get => m_ChildControlWidth; set => SetProperty(ref m_ChildControlWidth, value); }
    public bool childControlHeight { get => m_ChildControlHeight; set => SetProperty(ref m_ChildControlHeight, value); }
    public bool childScaleWidth { get => m_ChildScaleWidth; set => SetProperty(ref m_ChildScaleWidth, value); }
    public bool childScaleHeight { get => m_ChildScaleHeight; set => SetProperty(ref m_ChildScaleHeight, value); }

    // ── Private state ──────────────────────────────────────────────
    private readonly List<float> m_ChildWidths = new List<float>();
    private readonly List<float> m_ChildHeights = new List<float>();

    // ── Helpers ────────────────────────────────────────────────────

    private void GatherChildSizes() {
        m_ChildWidths.Clear();
        m_ChildHeights.Clear();
        foreach (RectTransform child in rectChildren) {
            float w = m_ChildControlWidth ? LayoutUtility.GetPreferredWidth(child) : child.sizeDelta.x;
            float h = m_ChildControlHeight ? LayoutUtility.GetPreferredHeight(child) : child.sizeDelta.y;
            if (m_ChildScaleWidth) w *= child.localScale.x;
            if (m_ChildScaleHeight) h *= child.localScale.y;
            m_ChildWidths.Add(w);
            m_ChildHeights.Add(h);
        }
    }

    /// <summary>
    /// Groups child indices into rows (horizontal flow) or columns (vertical flow)
    /// based on how many fit within the container's main-axis size.
    /// </summary>
    private List<List<int>> BuildLines(bool horizontal) {
        float innerMain = horizontal
            ? rectTransform.rect.width - m_Padding.horizontal
            : rectTransform.rect.height - m_Padding.vertical;
        float gap = horizontal ? m_Spacing.x : m_Spacing.y;

        var lines = new List<List<int>>();
        var current = new List<int>();
        float cursor = 0f;

        for (int i = 0; i < rectChildren.Count; i++) {
            float childMain = horizontal ? m_ChildWidths[i] : m_ChildHeights[i];

            if (current.Count > 0 && cursor + childMain > innerMain + 0.001f) {
                lines.Add(current);
                current = new List<int>();
                cursor = 0f;
            }

            current.Add(i);
            cursor += childMain + gap;
        }

        if (current.Count > 0)
            lines.Add(current);

        return lines;
    }

    // ── LayoutGroup overrides ──────────────────────────────────────

    public override void CalculateLayoutInputHorizontal() {
        base.CalculateLayoutInputHorizontal(); // populates rectChildren
        GatherChildSizes();

        // Min width  = padding + widest single child (worst-case: 1 child per row)
        // Pref width = padding + all children in one row
        float maxChild = 0f, totalAll = 0f;
        for (int i = 0; i < m_ChildWidths.Count; i++) {
            if (m_ChildWidths[i] > maxChild) maxChild = m_ChildWidths[i];
            totalAll += m_ChildWidths[i] + (i > 0 ? m_Spacing.x : 0f);
        }

        SetLayoutInputForAxis(
            m_Padding.horizontal + maxChild,
            m_Padding.horizontal + totalAll,
            -1f, 0);
    }

    public override void CalculateLayoutInputVertical() {
        GatherChildSizes();
        bool horizontal = m_StartAxis == Axis.Horizontal;
        var lines = BuildLines(horizontal);

        float crossGap = horizontal ? m_Spacing.y : m_Spacing.x;
        float crossPad = horizontal ? m_Padding.vertical : m_Padding.horizontal;

        float total = crossPad;
        for (int l = 0; l < lines.Count; l++) {
            float lineSize = 0f;
            foreach (int idx in lines[l])
                lineSize = Mathf.Max(lineSize, horizontal ? m_ChildHeights[idx] : m_ChildWidths[idx]);
            total += lineSize + (l < lines.Count - 1 ? crossGap : 0f);
        }

        SetLayoutInputForAxis(total, total, -1f, 1);
    }

    public override void SetLayoutHorizontal() {
        GatherChildSizes();
        ApplyLayout(settingAxis: 0);
    }

    public override void SetLayoutVertical() {
        GatherChildSizes();
        ApplyLayout(settingAxis: 1);
    }

    // ── Core placement ─────────────────────────────────────────────

    private void ApplyLayout(int settingAxis) {
        bool horizontal = m_StartAxis == Axis.Horizontal;
        int mainAxis = horizontal ? 0 : 1;
        int crossAxis = horizontal ? 1 : 0;

        float innerWidth = rectTransform.rect.width - m_Padding.horizontal;
        float innerHeight = rectTransform.rect.height - m_Padding.vertical;
        float containerMain = horizontal ? innerWidth : innerHeight;
        float containerCross = horizontal ? innerHeight : innerWidth;

        float mainGap = horizontal ? m_Spacing.x : m_Spacing.y;
        float crossGap = horizontal ? m_Spacing.y : m_Spacing.x;

        bool expandMain = horizontal ? m_ChildForceExpandWidth : m_ChildForceExpandHeight;
        bool expandCross = horizontal ? m_ChildForceExpandHeight : m_ChildForceExpandWidth;
        bool controlMain = horizontal ? m_ChildControlWidth : m_ChildControlHeight;
        bool controlCross = horizontal ? m_ChildControlHeight : m_ChildControlWidth;

        var lines = BuildLines(horizontal);

        // Compute the cross-axis size for each line (row height / column width)
        var lineCross = new float[lines.Count];
        for (int l = 0; l < lines.Count; l++)
            foreach (int idx in lines[l])
                lineCross[l] = Mathf.Max(lineCross[l],
                    horizontal ? m_ChildHeights[idx] : m_ChildWidths[idx]);

        // Spread extra cross space evenly across lines when force-expanding
        if (expandCross && lines.Count > 0) {
            float used = 0f;
            foreach (float s in lineCross) used += s;
            used += Mathf.Max(0, lines.Count - 1) * crossGap;
            float extra = Mathf.Max(0f, containerCross - used) / lines.Count;
            for (int l = 0; l < lineCross.Length; l++)
                lineCross[l] += extra;
        }

        float crossStart = horizontal ? m_Padding.top : m_Padding.left;

        for (int l = 0; l < lines.Count; l++) {
            List<int> line = lines[l];

            // Total main space consumed by children in this line (without expansion)
            float usedMain = 0f;
            foreach (int idx in line)
                usedMain += horizontal ? m_ChildWidths[idx] : m_ChildHeights[idx];
            usedMain += Mathf.Max(0, line.Count - 1) * mainGap;

            float perExtra = expandMain && line.Count > 0
                ? Mathf.Max(0f, containerMain - usedMain) / line.Count
                : 0f;

            float mainStart = horizontal ? m_Padding.left : m_Padding.top;

            foreach (int idx in line) {
                RectTransform child = rectChildren[idx];
                float childMain = (horizontal ? m_ChildWidths[idx] : m_ChildHeights[idx]) + perExtra;
                float childCross = expandCross || controlCross
                    ? (expandCross ? lineCross[l] : (horizontal ? m_ChildHeights[idx] : m_ChildWidths[idx]))
                    : (horizontal ? child.sizeDelta.y : child.sizeDelta.x);

                if (settingAxis == mainAxis) {
                    if (controlMain || expandMain)
                        SetChildAlongAxis(child, mainAxis, mainStart, childMain);
                    else
                        SetChildAlongAxis(child, mainAxis, mainStart);
                } else {
                    if (controlCross || expandCross)
                        SetChildAlongAxis(child, crossAxis, crossStart, childCross);
                    else
                        SetChildAlongAxis(child, crossAxis, crossStart);
                }

                mainStart += childMain + mainGap;
            }

            crossStart += lineCross[l] + crossGap;
        }
    }
}