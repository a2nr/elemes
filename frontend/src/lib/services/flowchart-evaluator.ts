export interface FlowchartEvalResult {
	pass: boolean;
	score: number;
	output: string;
	feedback: string[];
}

interface ParsedGraph {
    nodes: Map<string, { type: string; text: string }>;
    edges: Array<{ from: string; to: string; label: string }>;
}

function parseToGraph(text: string): ParsedGraph {
    const nodes = new Map<string, { type: string; text: string }>();
    const edges: Array<{ from: string; to: string; label: string }> = [];
    
    const nodeRegex = /^(\w+)(?:\[(\w+)\])?(?:\s+"([^"]+)")?$/;
    const edgeRegex = /^(\w+)\s*-->\s*(\w+)(?:\s+"([^"]+)")?$/;

    const lines = text.split('\n');
    for (let line of lines) {
        line = line.trim();
        if (!line || line.startsWith('#') || line.startsWith('//')) continue;

        const edgeMatch = line.match(edgeRegex);
        if (edgeMatch) {
            const [, u, v, label] = edgeMatch;
            edges.push({ from: u, to: v, label: (label || "").toLowerCase().trim() });
            continue;
        }

        const nodeMatch = line.match(nodeRegex);
        if (nodeMatch) {
            const [, id, type, nodeText] = nodeMatch;
            nodes.set(id, {
                type: type || "rect",
                text: (nodeText || id).toLowerCase().trim()
            });
        }
    }
    return { nodes, edges };
}

/**
 * Evaluates student flowchart against reference using keyword and connection matching.
 */
export function evaluateFlowchartSubmission(
    studentText: string,
    referenceText: string
): FlowchartEvalResult {
    if (!referenceText) {
        return { pass: true, score: 100, output: "Luar biasa! Alur logika Anda sempurna.", feedback: [] };
    }

    const student = parseToGraph(studentText);
    const reference = parseToGraph(referenceText);
    
    let totalPoints = 0;
    const feedback: string[] = [];

    // 1. Keyword Matching (40 points)
    const refTexts = Array.from(reference.nodes.values()).map(n => n.text);
    const stuTexts = Array.from(student.nodes.values()).map(n => n.text);
    
    let foundKeywords = 0;
    for (const refText of refTexts) {
        const found = stuTexts.some(st => st.includes(refText) || refText.includes(st));
        if (found) {
            foundKeywords++;
        } else {
            feedback.push(`❌ Kurang instruksi: "${refText}"`);
        }
    }

    const keywordScore = refTexts.length > 0 ? (foundKeywords / refTexts.length) * 40 : 40;
    totalPoints += keywordScore;

    // 2. Connection Matching (60 points)
    // Map student IDs to reference IDs based on keyword matching
    const idMap = new Map<string, string>();
    for (const [sId, sNode] of student.nodes.entries()) {
        for (const [rId, rNode] of reference.nodes.entries()) {
            if (sNode.text.includes(rNode.text) || rNode.text.includes(sNode.text)) {
                idMap.set(sId, rId);
                break;
            }
        }
    }

    const stuEdgesMapped = student.edges
        .filter(e => idMap.has(e.from) && idMap.has(e.to))
        .map(e => ({ from: idMap.get(e.from)!, to: idMap.get(e.to)!, label: e.label }));

    let foundEdges = 0;
    for (const refEdge of reference.edges) {
        const found = stuEdgesMapped.some(se => 
            se.from === refEdge.from && se.to === refEdge.to
        );
        
        if (found) {
            foundEdges++;
        } else {
            const uText = reference.nodes.get(refEdge.from)?.text || refEdge.from;
            const vText = reference.nodes.get(refEdge.to)?.text || refEdge.to;
            feedback.push(`❌ Alur terputus: "${uText}" harus terhubung ke "${vText}"`);
        }
    }

    const connectionScore = reference.edges.length > 0 ? (foundEdges / reference.edges.length) * 60 : 60;
    totalPoints += connectionScore;

    const finalScore = Math.round(totalPoints);
    const pass = finalScore >= 70;

    if (pass && feedback.length === 0) {
        feedback.push("✅ Luar biasa! Alur logika Anda sempurna.");
    } else if (pass) {
        feedback.push("⚠️ Alur logika cukup baik, tapi ada beberapa bagian yang kurang tepat.");
    }

    return {
        pass,
        score: finalScore,
        output: feedback.join('\n'),
        feedback
    };
}
