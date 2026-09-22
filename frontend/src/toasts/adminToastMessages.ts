const action = (success: string, error: string) => ({ success, error })

export const ADMIN_TOASTS = {
  product: {
    create: action('Producto creado correctamente.', 'No se pudo crear el producto.'),
    update: action('Producto actualizado correctamente.', 'No se pudo actualizar el producto.'),
    remove: action('Producto eliminado correctamente.', 'No se pudo eliminar el producto.'),
  },
  image: {
    add: action('Imagen agregada correctamente.', 'No se pudo agregar la imagen.'),
    primary: action('Imagen principal actualizada correctamente.', 'No se pudo actualizar la imagen principal.'),
    remove: action('Imagen eliminada correctamente.', 'No se pudo eliminar la imagen.'),
  },
  specification: {
    create: action('Especificación creada correctamente.', 'No se pudo crear la especificación.'),
    update: action('Especificación actualizada correctamente.', 'No se pudo actualizar la especificación.'),
    remove: action('Especificación eliminada correctamente.', 'No se pudo eliminar la especificación.'),
  },
  technicalSheet: {
    create: action('Ficha técnica agregada correctamente.', 'No se pudo agregar la ficha técnica.'),
    update: action('Ficha técnica actualizada correctamente.', 'No se pudo actualizar la ficha técnica.'),
    replace: action('Archivo de ficha técnica reemplazado correctamente.', 'No se pudo reemplazar el archivo de la ficha técnica.'),
    remove: action('Ficha técnica eliminada correctamente.', 'No se pudo eliminar la ficha técnica.'),
  },
  category: {
    create: action('Categoría creada correctamente.', 'No se pudo crear la categoría.'),
    update: action('Categoría actualizada correctamente.', 'No se pudo actualizar la categoría.'),
    remove: action('Categoría eliminada correctamente.', 'No se pudo eliminar la categoría.'),
  },
  brand: {
    create: action('Marca creada correctamente.', 'No se pudo crear la marca.'),
    update: action('Marca actualizada correctamente.', 'No se pudo actualizar la marca.'),
    remove: action('Marca eliminada correctamente.', 'No se pudo eliminar la marca.'),
  },
  supplier: {
    create: action('Proveedor creado correctamente.', 'No se pudo crear el proveedor.'),
    update: action('Proveedor actualizado correctamente.', 'No se pudo actualizar el proveedor.'),
    deactivate: action('Proveedor desactivado correctamente.', 'No se pudo desactivar el proveedor.'),
  },
  customer: {
    create: action('Cliente creado correctamente.', 'No se pudo crear el cliente.'),
    update: action('Cliente actualizado correctamente.', 'No se pudo actualizar el cliente.'),
    deactivate: action('Cliente desactivado correctamente.', 'No se pudo desactivar el cliente.'),
    reactivate: action('Cliente reactivado correctamente.', 'No se pudo reactivar el cliente.'),
  },
  quoteRequest: { status: action('Estado de la solicitud actualizado correctamente.', 'No se pudo actualizar el estado de la solicitud.') },
  commercialQuote: { issue: action('Cotización emitida correctamente.', 'No se pudo emitir la cotización.') },
  promotion: {
    create: action('Oferta creada correctamente.', 'No se pudo crear la oferta.'),
    update: action('Oferta actualizada correctamente.', 'No se pudo actualizar la oferta.'),
    deactivate: action('Oferta desactivada correctamente.', 'No se pudo desactivar la oferta.'),
  },
  homeSection: {
    create: action('Producto agregado a la portada correctamente.', 'No se pudo agregar el producto a la portada.'),
    reorder: action('Orden de portada actualizado correctamente.', 'No se pudo actualizar el orden de portada.'),
    remove: action('Producto quitado de la portada correctamente.', 'No se pudo quitar el producto de la portada.'),
  },
  user: {
    create: action('Usuario creado correctamente.', 'No se pudo crear el usuario.'),
    update: action('Usuario actualizado correctamente.', 'No se pudo actualizar el usuario.'),
    deactivate: action('Usuario desactivado correctamente.', 'No se pudo desactivar el usuario.'),
    reactivate: action('Usuario reactivado correctamente.', 'No se pudo reactivar el usuario.'),
    password: action('Contraseña actualizada. Ingresa nuevamente.', 'No se pudo actualizar la contraseña.'),
  },
} as const
