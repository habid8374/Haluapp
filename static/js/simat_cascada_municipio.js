/*
 * Cascada Departamento → Municipio (SIMAT).
 *
 * Cuando el usuario elige un departamento, el desplegable de municipio se reduce
 * a los municipios de ese departamento. Empareja cada par por el nombre del
 * campo (departamento_X ↔ municipio_X), así funciona con o sin prefijo de form.
 *
 * Requisitos (los pone simat.widgets):
 *  - el <select> de departamento lleva la clase .js-depto-filtro
 *  - cada <option> de municipio lleva data-departamento="<id_departamento>"
 */
(function () {
  function nombreMunicipio(depto) {
    return depto.name.replace('departamento', 'municipio');
  }

  function filtrar(depto, muni) {
    // Guarda una sola vez todas las opciones originales.
    if (!muni._todas) {
      muni._todas = Array.prototype.slice.call(muni.options);
    }
    var seleccion = muni.value;
    var val = depto.value;

    // Vacía el select y vuelve a agregar solo lo que corresponde.
    while (muni.options.length) { muni.remove(0); }

    var conservaSeleccion = false;
    muni._todas.forEach(function (op) {
      var d = op.getAttribute('data-departamento');
      // La opción vacía (sin data-departamento) siempre; las demás solo si
      // coinciden con el departamento elegido. Sin departamento → se muestran
      // todas (aún no hay filtro).
      if (!d || !val || d === val) {
        muni.add(op);
        if (op.value === seleccion) { conservaSeleccion = true; }
      }
    });

    muni.value = conservaSeleccion ? seleccion : '';
  }

  function init() {
    var deptos = document.querySelectorAll('select.js-depto-filtro');
    Array.prototype.forEach.call(deptos, function (depto) {
      var form = depto.form;
      if (!form) { return; }
      var muni = form.querySelector('select[name="' + nombreMunicipio(depto) + '"]');
      if (!muni) { return; }
      filtrar(depto, muni);
      depto.addEventListener('change', function () { filtrar(depto, muni); });
    });
  }

  if (document.readyState !== 'loading') { init(); }
  else { document.addEventListener('DOMContentLoaded', init); }
})();
