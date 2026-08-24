import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { getContract, signContract } from "../api/contracts";
import { listClients } from "../api/clients";
import SignaturePad from "../components/SignaturePad";

export default function FirmarContrato() {
  const { contractId } = useParams<{ contractId: string }>();
  const id = contractId!;
  const queryClient = useQueryClient();

  const { data: contract } = useQuery({ queryKey: ["contract", id], queryFn: () => getContract(id) });
  const { data: clients = [] } = useQuery({ queryKey: ["clients"], queryFn: listClients });

  const client = clients.find((c) => c.id === contract?.client_id);

  const [signerName, setSignerName] = useState("");
  const [signerId, setSignerId] = useState("");
  const [signatureImage, setSignatureImage] = useState<string | null>(null);

  const signMutation = useMutation({
    mutationFn: () =>
      signContract(id, {
        signer_name: signerName || client?.full_name || "",
        signer_identification: signerId || client?.identification || null,
        signature_image: signatureImage!,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["contract", id] }),
    onError: (err) => alert(axiosErrorMessage(err) ?? "No se pudo registrar la firma."),
  });

  if (!contract) return <p className="p-6 text-sm text-slate-500">Cargando...</p>;

  if (contract.status !== "draft") {
    return (
      <div className="max-w-2xl mx-auto p-8 print:p-0">
        <div className="flex items-center justify-between mb-6 print:hidden">
          <h1 className="text-lg font-semibold text-slate-800">Contrato {contract.status === "signed" ? "firmado" : "anulado"}</h1>
          <button onClick={() => window.print()} className="bg-slate-900 text-white text-sm rounded px-4 py-2">
            Imprimir
          </button>
        </div>
        <div className="border rounded-lg p-6 space-y-4">
          <p className="text-sm whitespace-pre-wrap">{contract.rendered_body}</p>
          {contract.signature_image && (
            <div className="border-t pt-4">
              <h3 className="text-sm font-medium text-slate-600 mb-1">Firma</h3>
              <img src={contract.signature_image} alt="Firma" className="border rounded bg-white" style={{ maxWidth: 300 }} />
              <p className="text-xs text-slate-500 mt-1">
                {contract.signer_name}
                {contract.signer_identification ? ` — doc. ${contract.signer_identification}` : ""}
              </p>
              <p className="text-xs text-slate-400">
                Firmado el {contract.signed_at ? new Date(contract.signed_at).toLocaleString() : "—"} desde IP{" "}
                {contract.signer_ip ?? "—"}
              </p>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-lg font-semibold text-slate-800 mb-6">Firmar contrato</h1>
      <div className="border rounded-lg p-6 space-y-4 bg-white">
        <p className="text-sm whitespace-pre-wrap">{contract.rendered_body}</p>

        <div className="border-t pt-4 grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-slate-500 mb-1">Nombre de quien firma</label>
            <input
              value={signerName}
              onChange={(e) => setSignerName(e.target.value)}
              placeholder={client?.full_name ?? ""}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Documento</label>
            <input
              value={signerId}
              onChange={(e) => setSignerId(e.target.value)}
              placeholder={client?.identification ?? ""}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </div>
        </div>

        <div className="border-t pt-4">
          <SignaturePad onChange={setSignatureImage} />
        </div>

        <button
          onClick={() => signMutation.mutate()}
          disabled={signMutation.isPending || !signatureImage}
          className="bg-slate-900 text-white text-sm rounded px-4 py-2 disabled:opacity-50"
        >
          Confirmar firma
        </button>
      </div>
    </div>
  );
}

function axiosErrorMessage(err: unknown): string | null {
  if (typeof err === "object" && err !== null && "response" in err) {
    const response = (err as { response?: { data?: { detail?: unknown } } }).response;
    const detail = response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return null;
}
