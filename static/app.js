
import * as pc from './playcanvas.mjs'

const canvas = document.createElement('canvas');
canvas.style.width = "100%";
canvas.style.height = "100%";
canvas.style.display = "block";

pc.WasmModule.setConfig('Ammo', {
    glueUrl: '/static/ammo.wasm.js',
    wasmUrl: '/static/ammo.wasm.wasm',
    fallbackUrl: '/static/ammo.js'
});
await new Promise((resolve) => {
    pc.WasmModule.getInstance('Ammo', () => resolve());
});

/* Place the canvas in the 'view' portion of the page */
document.getElementById('view').appendChild(canvas);

const app = new pc.Application(canvas, {
    mouse: new pc.Mouse(document.body)
});

// fill the available space at full resolution
app.setCanvasFillMode(pc.FILLMODE_FILL_WINDOW);
app.setCanvasResolution(pc.RESOLUTION_AUTO);

// ensure canvas is resized when window changes size
window.addEventListener('resize', () => app.resizeCanvas());

// create camera entity
const camera = new pc.Entity('camera');
camera.addComponent('camera', {
    clearColor: new pc.Color(1.0, 1.0, 1.0)
});
camera.camera.projection = pc.PROJECTION_ORTHOGRAPHIC;
app.root.addChild(camera);
camera.setPosition(0, 0, 0);

// create directional light entity
const light = new pc.Entity('light');
light.addComponent('light');
app.root.addChild(light);
light.setEulerAngles(45, 0, 0);

/* Add event listener for upload button */
const pcb_input_item = document.getElementById('pcbUpload');
pcb_input_item.addEventListener("change", handle_file_upload);

const pos_input_item = document.getElementById('posUpload');
pos_input_item.addEventListener("change", handle_pos_file_upload);

const bom_upload = document.getElementById("bomUpload");
bom_upload.addEventListener("change", handle_bom_upload);

let curr_component = document.getElementById("currComp");
curr_component.textContent = "";

let component_table = document.getElementById("comp-table");

const bom_popup = document.getElementById("bomPrompt");
const bp_close = document.getElementById("closeBpPopup");
const bp_save = document.getElementById("saveBpChoice");
const component_search = document.getElementById("search");

bp_save.addEventListener("click", handle_save_bom_item);
bp_close.addEventListener("click", close_bp_popup);
component_search.addEventListener("keyup", handle_query_request);

app.start();
app.mouse.on(pc.EVENT_MOUSEDOWN, on_mouse_down);

var previous_material = null;

const board_width_mm = 51;
let pcb_mm_to_world = 1.1;


function on_mouse_down(event) {

    if (event.button == 0) {

        const from = camera.camera.screenToWorld(event.x, event.y, camera.camera.nearClip);
        const to = camera.camera.screenToWorld(event.x, event.y, camera.camera.farClip);
        const result = app.systems.rigidbody.raycastFirst(from, to);

        if (result ) {
            const entity = result.entity;
            curr_component.textContent = entity.name;
        
            get_options_for_component(entity.name);
        }
        else{
            console.log("miss");
        }
    }
}

function format_standard_pricing(prices)
{
    let split_str = prices.split(" ");
    let contents = "";

    for(var i = 0; i < split_str.length; i++)
    {
        if (i % 3 === 0 && split_str[i + 2])
            contents += `${split_str[i]} ${split_str[i + 1]} ${split_str[i + 2]}<br>`
    }

    return contents;
}

function format_hyperlinks(link)
{
    return `<a href="${link}" target="_blank">Digikey</a>`;
}
function format_row(data)
{
    const content = [
        data["Manufacturer"],
        data["Quantity"],
        data["Product Number"],
        data["Value"],
        // data["Footprint"],
        "0603",
        format_standard_pricing(data["Standard Pricing"]),
        // data["Standard Pricing"],
        format_hyperlinks(data["URL"])
    ]

    return content;
}

function toggle_popup(popup,visible)
{
    if(visible)
        popup.style.display = "block";
    else
        popup.style.display = "none";
}

function handle_component_selected(component)
{
    console.log("Clicked component ", component)

    toggle_popup(bom_popup, true);

    const replace_string = "Replace " + curr_component.textContent 
    + " With " + component["Product Number"] + "?";

    document.getElementById("bp-designator").innerHTML = replace_string;
}

function handle_save_bom_item()
{

}

function handle_query_request(event)
{   
    console.log("Handling query request");

    if(event.key == 'Enter')
    {
        let content = component_search.value
        if(content != "")
        {
            fetch(`/request-query?content=${content}`)
            .then(res => res.json())
            .then(data => {
                populate_table(data);
            })
        } 
        content = "";
        component_search.value = content;
    }

}

function populate_table(data)
{
    const table_body = component_table.querySelector("tbody");
    table_body.innerHTML = "";
    
    data.forEach(product => {
        const row = table_body.insertRow();
        const contents = format_row(product);
        row.data = product
        
        row.addEventListener("click", () => {
            handle_component_selected(product)
        })
            
        contents.forEach(c => {
            const cell = row.insertCell();
            cell.innerHTML = c;
        });
    })
}
function close_bp_popup()
{
    toggle_popup(bom_popup, false);
    document.getElementById("bp-designator").innerHTML = "";
}

/**
 * @brief Handles querying the backend to get a default set of available
 * component options when one has been selected
 */
function get_options_for_component(component_name) 
{
    fetch(`/request-parts?name=${component_name}&y=${component_name}`)
    .then(res => res.json())
    .then(data => {
        populate_table(data);
    });
}

/**
 * @brief Handles updating the bill of materials reference designator item
 * based on the selection from the user
 * @param item 
 */
function update_bom_item(item) {

}

/**
 * @brief Handles adjusting the camera after uploading a PCB view
 * so we always have a top-down view of the board. 
 * @note For the basic demo, we will just demonstrate a top down view of a board only 
 * having components on the top copper. In the future, we can support more complex 
 * camera operations, such as being able to arbitrariliy change the position of the board.
 * 
 * See https://forum.playcanvas.com/t/calculate-bounding-box-of-hierarchy-of-objects/31512/3
 * For further explanation
 */
function adjust_camera_view(entity) {

    /**
     * All entities [PCB entity i.e] have meshes defining the shape.
     * All individual meshes have a bounding box defining size. Therefore,
     * the bounding box of the total entity is found by summing the individual
     * bounding boxes of the meshes.
     */
    const meshes = entity.model.meshInstances;
    const len_meshes = meshes.length;

    if (len_meshes > 0) {
        var bounding_box = new pc.BoundingBox();
        bounding_box.copy(meshes[0].aabb);
        for (var i = 1; i < len_meshes; i++) {
            bounding_box.add(meshes[i].aabb);
        }
        console.log(bounding_box);
    }

    /* Bounding box contains 'halfExtents' and 'Center' vector */
    const extents = bounding_box.halfExtents;
    const entity_center = bounding_box.center;


    /**
     * Since the camera is looking straight down, then the only dimensions
     * in the vector that are changing are X,Z - that is, the total distance
     * the camera needs to be 'backed up' depends on whether the greater magnitude
     * is present in the X or Z direction. extents.y essentially means the highest
     * point of the entity, therefore, we need to add that to the y_pos as well to clear
     * the highest point.
     */
    const max_magnitude = extents.z > extents.x ? extents.z : extents.x;
    const camera_y_pos = entity_center.y + extents.y + max_magnitude * 2;

    /**
     * The camera is centered in the bounding box, but need to apply an offset to the 
     * camera such that the model appears centered in the canvas
     * 
     * Use orthographic projection - total visible width depends on the 
     * camera orthogonal height and aspect ratio.
     * 
     * Total view width / canvas width gives world units per pixel
     * So the offset we should apply to the camera center is determined by the center
     * of the canvas position (pixels) into the world units per pixel ratio
     * 
     * This places entity x center in camera center which is the center of the canvas
     */

    const canvas_bounds = canvas.getBoundingClientRect();
    const center_of_canvas = canvas_bounds.width / 2;
    const aspect_ratio = canvas_bounds.width / canvas_bounds.height;
    const total_view_width = 2 * camera.camera.orthoHeight * aspect_ratio;
    const offset = Math.round(center_of_canvas * (total_view_width / canvas_bounds.width));


    const boxSize = new pc.Vec3(5,1,5);
    var y = 0;
//     for(var y = 0; y < 8; y++)
//     {
// //   
//         const box = new pc.Entity("box" + y);

//     // Add visual shape
//     box.addComponent("model", { type: "box" });

//     // Add collider
//     box.addComponent("collision", {
//         type: "box",
//         halfExtents: new pc.Vec3(2.5, 0.5, 2.5)
//     });

//     box.addComponent("rigidbody", { type: "static" }); 
//     box.setLocalScale(5,1,5);

// const mat = new pc.StandardMaterial();
// mat.diffuse = new pc.Color(1, 0, 0);  // Red box
// mat.update();
// box.model.material = mat;

//     const xPos = entity_center.x + offset - (y * 10);
//     const yPos = entity_center.y + extents.y + boxSize.y / 2 + 0.05; // just above PCB
//     const zPos = entity_center.z;

//     console.log(yPos);
//     console.log(zPos);
//     box.setPosition(xPos, 10, zPos);
//     app.root.addChild(box);

//     // box.setPosition(camera.camera.x + (y * 10), 0, 0);
// // box.setLocalScale(0.75, 0.75, 1);

// }
    camera.setPosition(entity_center.x + offset, camera_y_pos + offset, entity_center.z);
    camera.lookAt(entity_center.x + offset, entity_center.y, entity_center.z);
    camera.camera.orthoHeight = extents.z + 30;
    pcb_mm_to_world = (extents.x * 2) / board_width_mm;
}

function handle_bom_upload(event)
{
    const fdata = new FormData();
    const file = bom_upload.files[0];
    fdata.append('file', file);

    fetch('/upload', {
        method: 'POST',
        body: fdata
    }).then(res => res.json())
    .then(data => {
        console.log(data);
    });
}

function handle_pos_file_upload(event)
{
    
    const fdata = new FormData();
    const file = pos_input_item.files[0];
    fdata.append('file', file);

    fetch('/upload', {
        method: 'POST',
        body: fdata
    })
    .then(res => res.json())
    .then(data => {
        data.forEach(c => {
            create_component_collision_boxes(c.name, c.x, c.y, c.z, c.width, c.height, c.depth)
        });
    });
}

var incr = 0;
/**
 * @brief Create a collision box for each PCB component in order to 
 * use PC raytracing on them
 */
function create_component_collision_boxes(component_name, x, y, z, width, height, depth)
{
    const cbox = new pc.Entity(component_name);
    x = x * pcb_mm_to_world;
    y = y * pcb_mm_to_world;
    z = z * pcb_mm_to_world;
    width = width * pcb_mm_to_world;
    height = height * pcb_mm_to_world;

    /* Relate the relative dimensions of the components to the world */
    
    const box = new pc.Entity(component_name);
    const box_size = new pc.Vec3(width, 2, height);

    box.addComponent("model", { type: "box" });
    box.addComponent("collision", {
        type: "box",
        halfExtents: new pc.Vec3(box_size.x / 2, box_size.y / 2, box_size.z / 2)
        // halfExtents: new pc.Vec3(2.5,0.5, 2.5)
    });
    
    box.addComponent("rigidbody", { type: "static" }); 
    box.setLocalScale(box_size);

    const mat = new pc.StandardMaterial();
    mat.diffuse = new pc.Color(1, 0, 0);
    mat.update();
    box.model.material = mat;

    const xPos = x;
    // const yPos = entity_center.y + extents.y + boxSize.y / 2 + 0.05; // just above PCB
    // const zPos = entity_center.z;
    const yPos = 30.55
    const zPos = 3.76;

    /**
     * Since we're doing an orthographic projection, Y axis is constant and the vertical
     * axis is represented by the Z axis. Therefore, Y pos in the file will be used for 
     * vertical positioning (Z)
     */
    box.setPosition(x, 5,y * -1);
    app.root.addChild(box);
    incr++;
}
/**
 * @brief Takes the user supplied 3D PCB view and renders it to scene
 * @param {*} event 
 * @returns 
 */
function handle_file_upload(event) {

    const file = event.target.files[0];

    if (!file)
        return;

    const reader = new FileReader();

    /* FileReader succesfully loaded file, begin adding to PC engine */
    reader.onload = (blb) => {

        const buf = blb.target.result;
        const blob = new Blob([buf], { type: 'model/gltf-binary' });
        const url = URL.createObjectURL(blob);

        app.assets.loadFromUrl(url, "container", on_pcb_loaded);
    }

    reader.onerror = () => {
        // TODO do something on error
    }

    reader.readAsArrayBuffer(file);
}

function on_pcb_loaded(error, asset) {
    if (error) {
        console.log("error");
        // TODO notify error
    }
    else {
        const pcb_entity = new pc.Entity();
        pcb_entity.addComponent("model", {
            type: "asset",
            asset: asset.resource.model,
        });

        /* Add entity to the scene */
        app.root.addChild(pcb_entity);

        /* Adjust the current camera */
        adjust_camera_view(pcb_entity);

        fetch("/update-qengine")
    }
}

function show_upload_status(message, type) {

}