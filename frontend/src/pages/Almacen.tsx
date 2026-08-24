import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createInventoryItem,
  createInventoryMovement,
  createSupplier,
  deleteInventoryItem,
  deleteSupplier,
  getBalanceByTechnician,
  listInventoryItems,
  listSuppliers,
  updateInventoryItem,
} from "../api/inventory";
import { listClients } from "../api/clients";
import { listStaffDirectory } from "../api/users";
import type {
  InventoryItem,
  InventoryItemInput,
  InventoryMovementInput,
  MovementReason,
  Supplier,
  SupplierInput,
} from "../api/types";
import Field from "../components/Field";

const emptySupplierForm: SupplierInput = { name: "", phone: "", email: "", notes: "" };
const emptyItemForm: InventoryItemInput = { name: "", category: "otro", unit_cost: null, supplier_id: null };
const emptyMovementForm: InventoryMovementInput = {
  item_id: "",
  reason: "purchase",
  quantity_delta: 1,
  assigned_to_user_id: null,
  client_id: null,
  note: "",
};

const reasonLabels: Record<MovementReason, string> = {
  purchase: "Compra",
  assignment: "Asignado a técnico",
  installation: "Instalado en cliente",
  return: "Devolución de técnico",
  adjustment: "Ajuste de conteo",
  loss: "Pérdida / rotura",
};

// La cantidad que se pide en el formulario siempre es positiva -- el signo
// real (sumar o restar del stock) lo decide el motivo, no el usuario.
const NEGATIVE_REASONS = new Set<MovementReason>(["assignment", "installation", "loss"]);

export default function Almacen() {
  const queryClient = useQueryClient();
  const { data: suppliers = [] } = useQuery({ queryKey: ["suppliers"], queryFn: listSuppliers });
  const { data: items = [] } = useQuery({ queryKey: ["inventory-items"], queryFn: listInventoryItems });
  const { data: balances = [] } = useQuery({
    queryKey: ["inventory-balance-by-technician"],
    queryFn: getBalanceByTechnician,
  });
  const { data: users = [] } = useQuery({ queryKey: ["staff-directory"], queryFn: listStaffDirectory });
  const { data: clients = [] } = useQuery({ queryKey: ["clients"], queryFn: listClients });

  const [supplierForm, setSupplierForm] = useState<SupplierInput>(emptySupplierForm);
  const [showSupplierForm, setShowSupplierForm] = useState(false);

  const [itemForm, setItemForm] = useState<InventoryItemInput>(emptyItemForm);
  const [showItemForm, setShowItemForm] = useState(false);
  const [editingItemId, setEditingItemId] = useState<string | null>(null);

  const [movementForm, setMovementForm] = useState<InventoryMovementInput>(emptyMovementForm);
  const [movementQuantity, setMovementQuantity] = useState(1);

  const createSupplierMutation = useMutation({
    mutationFn: createSupplier,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["suppliers"] });
      setSupplierForm(emptySupplierForm);
      setShowSupplierForm(false);
    },
  });

  const deleteSupplierMutation = useMutation({
    mutationFn: deleteSupplier,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["suppliers"] }),
    onError: (err) => alert(axiosErrorMessage(err) ?? "No se pudo borrar el proveedor."),
  });

  const createItemMutation = useMutation({
    mutationFn: createInventoryItem,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inventory-items"] });
      closeItemForm();
    },
  });

  const updateItemMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: InventoryItemInput }) =>
      updateInventoryItem(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inventory-items"] });
      closeItemForm();
    },
  });

  const deleteItemMutation = useMutation({
    mutationFn: deleteInventoryItem,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["inventory-items"] }),
    onError: (err) => alert(axiosErrorMessage(err) ?? "No se pudo borrar el artículo."),
  });

  const movementMutation = useMutation({
    mutationFn: createInventoryMovement,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inventory-items"] });
      queryClient.invalidateQueries({ queryKey: ["inventory-balance-by-technician"] });
      setMovementForm(emptyMovementForm);
      setMovementQuantity(1);
    },
    onError: (err) => alert(axiosErrorMessage(err) ?? "No se pudo registrar el movimiento."),
  });

  function closeItemForm() {
    setItemForm(emptyItemForm);
    setEditingItemId(null);
    setShowItemForm(false);
  }

  function startEditItem(item: InventoryItem) {
    setItemForm({
      name: item.name,
      category: item.category,
      unit_cost: item.unit_cost,
      supplier_id: item.supplier_id,
      notes: item.notes ?? "",
    });
    setEditingItemId(item.id);
    setShowItemForm(true);
  }

  function handleSupplierSubmit(e: FormEvent) {
    e.preventDefault();
    createSupplierMutation.mutate(supplierForm);
  }

  function handleItemSubmit(e: FormEvent) {
    e.preventDefault();
    if (editingItemId) {
      updateItemMutation.mutate({ id: editingItemId, payload: itemForm });
    } else {
      createItemMutation.mutate(itemForm);
    }
  }

  function handleMovementSubmit(e: FormEvent) {
    e.preventDefault();
    const sign = NEGATIVE_REASONS.has(movementForm.reason) ? -1 : 1;
    movementMutation.mutate({ ...movementForm, quantity_delta: sign * Math.abs(movementQuantity) });
  }

  function supplierName(id: string | null) {
    return suppliers.find((s) => s.id === id)?.name ?? "—";
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-800">Almacén</h1>

      {/* Proveedores */}
      <div className="bg-white rounded-lg shadow p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium text-slate-600">Proveedores</h2>
          <button
            onClick={() => setShowSupplierForm((s) => !s)}
            className="text-xs text-blue-600 hover:underline"
          >
            {showSupplierForm ? "Cancelar" : "Nuevo proveedor"}
          </button>
        </div>
        {showSupplierForm && (
          <form onSubmit={handleSupplierSubmit} className="grid grid-cols-3 gap-3 mb-4">
            <input
              required
              placeholder="Nombre"
              value={supplierForm.name}
              onChange={(e) => setSupplierForm({ ...supplierForm, name: e.target.value })}
              className="border rounded px-3 py-2 text-sm"
            />
            <input
              placeholder="Teléfono"
              value={supplierForm.phone ?? ""}
              onChange={(e) => setSupplierForm({ ...supplierForm, phone: e.target.value })}
              className="border rounded px-3 py-2 text-sm"
            />
            <input
              placeholder="Correo"
              value={supplierForm.email ?? ""}
              onChange={(e) => setSupplierForm({ ...supplierForm, email: e.target.value })}
              className="border rounded px-3 py-2 text-sm"
            />
            <button
              type="submit"
              disabled={createSupplierMutation.isPending}
              className="col-span-3 bg-slate-900 text-white text-sm rounded py-2 disabled:opacity-50"
            >
              Guardar proveedor
            </button>
          </form>
        )}
        <table className="w-full text-sm">
          <thead className="text-left text-slate-500">
            <tr>
              <th className="py-1">Nombre</th>
              <th className="py-1">Teléfono</th>
              <th className="py-1">Correo</th>
              <th className="py-1"></th>
            </tr>
          </thead>
          <tbody>
            {suppliers.map((s: Supplier) => (
              <tr key={s.id} className="border-t">
                <td className="py-1">{s.name}</td>
                <td className="py-1">{s.phone ?? "—"}</td>
                <td className="py-1">{s.email ?? "—"}</td>
                <td className="py-1">
                  <button
                    onClick={() => deleteSupplierMutation.mutate(s.id)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Eliminar
                  </button>
                </td>
              </tr>
            ))}
            {suppliers.length === 0 && (
              <tr>
                <td colSpan={4} className="py-4 text-center text-slate-400">
                  Aún no hay proveedores.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Artículos */}
      <div className="bg-white rounded-lg shadow p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium text-slate-600">Artículos</h2>
          <button
            onClick={() => (showItemForm ? closeItemForm() : setShowItemForm(true))}
            className="text-xs text-blue-600 hover:underline"
          >
            {showItemForm ? "Cancelar" : "Nuevo artículo"}
          </button>
        </div>
        {showItemForm && (
          <form onSubmit={handleItemSubmit} className="grid grid-cols-2 gap-3 mb-4">
            <Field label="Nombre">
              <input
                required
                value={itemForm.name}
                onChange={(e) => setItemForm({ ...itemForm, name: e.target.value })}
                className="border rounded px-3 py-2 text-sm w-full"
              />
            </Field>
            <Field label="Categoría">
              <input
                value={itemForm.category ?? ""}
                onChange={(e) => setItemForm({ ...itemForm, category: e.target.value })}
                placeholder="ej. router, antena, cable"
                className="border rounded px-3 py-2 text-sm w-full"
              />
            </Field>
            <Field label="Costo unitario (opcional)">
              <input
                type="number"
                step="0.01"
                value={itemForm.unit_cost ?? ""}
                onChange={(e) =>
                  setItemForm({ ...itemForm, unit_cost: e.target.value ? Number(e.target.value) : null })
                }
                className="border rounded px-3 py-2 text-sm w-full"
              />
            </Field>
            <Field label="Proveedor (opcional)">
              <select
                value={itemForm.supplier_id ?? ""}
                onChange={(e) => setItemForm({ ...itemForm, supplier_id: e.target.value || null })}
                className="border rounded px-3 py-2 text-sm w-full bg-white"
              >
                <option value="">Sin proveedor</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </Field>
            <button
              type="submit"
              disabled={createItemMutation.isPending || updateItemMutation.isPending}
              className="col-span-2 bg-slate-900 text-white text-sm rounded py-2 disabled:opacity-50"
            >
              {editingItemId ? "Actualizar artículo" : "Guardar artículo"}
            </button>
          </form>
        )}
        <table className="w-full text-sm">
          <thead className="text-left text-slate-500">
            <tr>
              <th className="py-1">Nombre</th>
              <th className="py-1">Categoría</th>
              <th className="py-1">Stock</th>
              <th className="py-1">Costo unitario</th>
              <th className="py-1">Proveedor</th>
              <th className="py-1"></th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-t">
                <td className="py-1">{item.name}</td>
                <td className="py-1">{item.category}</td>
                <td className="py-1 font-medium">{item.quantity}</td>
                <td className="py-1">{item.unit_cost != null ? `$${Number(item.unit_cost).toFixed(2)}` : "—"}</td>
                <td className="py-1">{supplierName(item.supplier_id)}</td>
                <td className="py-1 space-x-2">
                  <button onClick={() => startEditItem(item)} className="text-xs text-blue-600 hover:underline">
                    Editar
                  </button>
                  <button
                    onClick={() => deleteItemMutation.mutate(item.id)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Eliminar
                  </button>
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={6} className="py-4 text-center text-slate-400">
                  Aún no hay artículos.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Registrar movimiento */}
      <div className="bg-white rounded-lg shadow p-5">
        <h2 className="text-sm font-medium text-slate-600 mb-3">Registrar movimiento</h2>
        <form onSubmit={handleMovementSubmit} className="grid grid-cols-3 gap-3">
          <Field label="Artículo">
            <select
              required
              value={movementForm.item_id}
              onChange={(e) => setMovementForm({ ...movementForm, item_id: e.target.value })}
              className="border rounded px-3 py-2 text-sm w-full bg-white"
            >
              <option value="">Seleccionar...</option>
              {items.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} (stock: {item.quantity})
                </option>
              ))}
            </select>
          </Field>
          <Field label="Motivo">
            <select
              value={movementForm.reason}
              onChange={(e) => setMovementForm({ ...movementForm, reason: e.target.value as MovementReason })}
              className="border rounded px-3 py-2 text-sm w-full bg-white"
            >
              {(Object.keys(reasonLabels) as MovementReason[]).map((reason) => (
                <option key={reason} value={reason}>
                  {reasonLabels[reason]}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Cantidad">
            <input
              required
              type="number"
              min={1}
              value={movementQuantity}
              onChange={(e) => setMovementQuantity(Number(e.target.value))}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          {movementForm.reason === "assignment" || movementForm.reason === "return" ? (
            <Field label={movementForm.reason === "assignment" ? "Técnico" : "Técnico (opcional)"}>
              <select
                required={movementForm.reason === "assignment"}
                value={movementForm.assigned_to_user_id ?? ""}
                onChange={(e) =>
                  setMovementForm({ ...movementForm, assigned_to_user_id: e.target.value || null })
                }
                className="border rounded px-3 py-2 text-sm w-full bg-white"
              >
                <option value="">Seleccionar...</option>
                {users.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name}
                  </option>
                ))}
              </select>
            </Field>
          ) : null}
          {movementForm.reason === "installation" ? (
            <Field label="Cliente">
              <select
                required
                value={movementForm.client_id ?? ""}
                onChange={(e) => setMovementForm({ ...movementForm, client_id: e.target.value || null })}
                className="border rounded px-3 py-2 text-sm w-full bg-white"
              >
                <option value="">Seleccionar...</option>
                {clients.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.full_name}
                  </option>
                ))}
              </select>
            </Field>
          ) : null}
          <Field label="Nota (opcional)">
            <input
              value={movementForm.note ?? ""}
              onChange={(e) => setMovementForm({ ...movementForm, note: e.target.value })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <button
            type="submit"
            disabled={movementMutation.isPending || !movementForm.item_id}
            className="col-span-3 bg-slate-900 text-white text-sm rounded py-2 disabled:opacity-50"
          >
            Registrar movimiento
          </button>
        </form>
      </div>

      {/* Saldo por técnico */}
      <div className="bg-white rounded-lg shadow p-5">
        <h2 className="text-sm font-medium text-slate-600 mb-3">Material asignado por técnico</h2>
        <table className="w-full text-sm">
          <thead className="text-left text-slate-500">
            <tr>
              <th className="py-1">Técnico</th>
              <th className="py-1">Artículo</th>
              <th className="py-1">Cantidad</th>
            </tr>
          </thead>
          <tbody>
            {balances.map((b) => (
              <tr key={`${b.user_id}-${b.item_id}`} className="border-t">
                <td className="py-1">{b.user_name}</td>
                <td className="py-1">{b.item_name}</td>
                <td className="py-1 font-medium">{b.balance}</td>
              </tr>
            ))}
            {balances.length === 0 && (
              <tr>
                <td colSpan={3} className="py-4 text-center text-slate-400">
                  Ningún técnico tiene material asignado actualmente.
                </td>
              </tr>
            )}
          </tbody>
        </table>
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
