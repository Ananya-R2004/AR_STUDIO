import os
import io
import base64
import types
import requests
import time
import numpy as np
from PIL import Image

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

# --- CORRECTED Compatibility Shim for streamlit_drawable_canvas ---
# This must be BEFORE `from streamlit_drawable_canvas import st_canvas`

def _image_to_data_url(pil_image):
    """
    Convert a PIL Image to a data URL for streamlit_drawable_canvas.
    """
    if not isinstance(pil_image, Image.Image):
        # Handle cases where the input is not a PIL Image (e.g., None, int, etc.)
        return None

    buf = io.BytesIO()
    # The format should be "PNG" for transparency
    pil_image.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"

try:
    import streamlit.elements.image as _st_image_mod
    # The patch needs to be applied to the 'image' module within 'streamlit.elements'
    if hasattr(_st_image_mod, "image"):
        _st_image_mod = _st_image_mod.image
    if _st_image_mod and isinstance(_st_image_mod, types.ModuleType):
        setattr(_st_image_mod, "image_to_url", _image_to_data_url)
except (ImportError, AttributeError):
    pass
# --- End of Corrected Compatibility Shim ---


from streamlit_drawable_canvas import st_canvas

# --- Your other imports ---
from services import (
    enhance_prompt,
    generative_fill
)
from services.product_cutout import product_cutout  
from services.image_features import generate_background, remove_image_background, blur_background
from services.image_editing import erase_foreground
from services.image_expansion import expand_image
from services.hd_image_gen import generate_hd_image
from services.product_service import (
    create_product_packshot,
    add_product_shadow,
    create_lifestyle_shot_by_text
)

# Configure Streamlit page
st.set_page_config(
    page_title="AR Studio",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load environment variables
print("Loading environment variables...")
load_dotenv(verbose=True)  # Add verbose=True to see loading details

# Debug: Print environment variable status
api_key = os.getenv("BRIA_API_KEY")
print(f"API Key present: {bool(api_key)}")
print(f"API Key value: {api_key if api_key else 'Not found'}")
print(f"Current working directory: {os.getcwd()}")
print(f".env file exists: {os.path.exists('.env')}")

# For Product Shot Tools
if "packshot_image" not in st.session_state:
    st.session_state.packshot_image = None
if "shadow_image" not in st.session_state:
    st.session_state.shadow_image = None
if "lifestyle_images" not in st.session_state:
    st.session_state.lifestyle_images = []
if "pending_lifestyle_urls" not in st.session_state:
    st.session_state.pending_lifestyle_urls = []

# For Generative Fill (from previous code)
if "edited_image" not in st.session_state:
    st.session_state.edited_image = None
if "generated_images" not in st.session_state:
    st.session_state.generated_images = []
if "pending_urls" not in st.session_state: # For Generative Fill
    st.session_state.pending_urls = []

def initialize_session_state():
    """Initialize session state variables."""
    if 'api_key' not in st.session_state:
        st.session_state.api_key = os.getenv('BRIA_API_KEY')
    if 'generated_images' not in st.session_state:
        st.session_state.generated_images = []
    if 'current_image' not in st.session_state:
        st.session_state.current_image = None
    if 'pending_urls' not in st.session_state:
        st.session_state.pending_urls = []
    if 'edited_image' not in st.session_state:
        st.session_state.edited_image = None
    if 'original_prompt' not in st.session_state:
        st.session_state.original_prompt = ""
    if 'enhanced_prompt' not in st.session_state:
        st.session_state.enhanced_prompt = None

def download_image(url):
    """Download image from URL and return as bytes."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.content
    except Exception as e:
        st.error(f"Error downloading image: {str(e)}")
        return None

def apply_image_filter(image, filter_type):
    """Apply various filters to the image."""
    try:
        img = Image.open(io.BytesIO(image)) if isinstance(image, bytes) else Image.open(image)
        
        if filter_type == "Grayscale":
            return img.convert('L')
        elif filter_type == "Sepia":
            width, height = img.size
            pixels = img.load()
            for x in range(width):
                for y in range(height):
                    r, g, b = img.getpixel((x, y))[:3]
                    tr = int(0.393 * r + 0.769 * g + 0.189 * b)
                    tg = int(0.349 * r + 0.686 * g + 0.168 * b)
                    tb = int(0.272 * r + 0.534 * g + 0.131 * b)
                    img.putpixel((x, y), (min(tr, 255), min(tg, 255), min(tb, 255)))
            return img
        elif filter_type == "High Contrast":
            return img.point(lambda x: x * 1.5)
        elif filter_type == "Blur":
            return img.filter(Image.BLUR)
        else:
            return img
    except Exception as e:
        st.error(f"Error applying filter: {str(e)}")
        return None

def check_generated_images():
    """Check if pending images are ready and update the display."""
    if st.session_state.pending_urls:
        ready_images = []
        still_pending = []
        
        for url in st.session_state.pending_urls:
            try:
                response = requests.head(url)
                # Consider an image ready if we get a 200 response with any content length
                if response.status_code == 200:
                    ready_images.append(url)
                else:
                    still_pending.append(url)
            except Exception as e:
                still_pending.append(url)
        
        # Update the pending URLs list
        st.session_state.pending_urls = still_pending
        
        # If we found any ready images, update the display
        if ready_images:
            st.session_state.edited_image = ready_images[0]  # Display the first ready image
            if len(ready_images) > 1:
                st.session_state.generated_images = ready_images  # Store all ready images
            return True
            
    return False

def auto_check_images(status_container):
    """Automatically check for image completion a few times."""
    max_attempts = 3
    attempt = 0
    while attempt < max_attempts and st.session_state.pending_urls:
        time.sleep(2)  # Wait 2 seconds between checks
        if check_generated_images():
            status_container.success("✨ Image ready!")
            return True
        attempt += 1
    return False

def download_and_save_temp_image(url: str, directory: str = "temp_bria_results", prefix: str = "bria_output_"):
    """
    Downloads a file from a URL and saves it to a temporary directory.
    Returns the local path of the saved file.
    """
    if not url:
        return None

    os.makedirs(directory, exist_ok=True)
    
    # Extract filename from URL, or create a generic one
    filename = url.split('/')[-1].split('?')[0] # Remove query parameters
    if not filename or '.' not in filename:
        # Generate a unique filename if the URL doesn't provide a good one
        temp_filename_base = f"{prefix}{len(os.listdir(directory)) + 1}"
        file_extension = ".webm" if url.endswith(".webm") else ".png" # Assume common outputs
        filename = temp_filename_base + file_extension
    
    local_path = os.path.join(directory, filename)

    try:
        response = requests.get(url, stream=True, timeout=120) # Increased timeout for download
        response.raise_for_status()

        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return local_path
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Failed to download temporary image/video from Bria.ai: {e}")
        return None


def main():
    st.title("AR Studio")
    initialize_session_state()

    
    with st.sidebar:
        
        st.image("logo.png", use_container_width=True , width=120) # Slightly reduced width for more space

        # Stylish Brand Header
        st.markdown(
            "<h2 style='font-family:Verdana;color:white; text-align: left ;'>AR Studio</h2>",
            unsafe_allow_html=True
        )
        st.markdown(
            "Welcome to your creative playground powered by cutting edge AI. "
            "Unleash your imagination, transform your visuals, and create stunning content effortlessly."
        )

        st.markdown("---") # Divider

        # API Key Input - Connect to session state for persistence
        st.subheader("🔐 Access Key")
        
        current_api_key_input = st.text_input(
            "Default Bria AI API key:",
            type="password",
            value=st.session_state.api_key, # Link input to session state
            key="api_key_input_sidebar", # Unique key for this widget
            help="Your API key secures access to AI functionalities. Obtain it from Bria AI dashboard."
        )
        # Update session state only if the input value actually changed
        if current_api_key_input != st.session_state.api_key:
            st.session_state.api_key = current_api_key_input
            st.success("API Key updated!")


        st.markdown("---")

        #  What's New / Highlights 
        st.subheader(" Highlights & Innovations")
        st.markdown(
            """
            Dive into the forefront of AI-powered visual creation:

            * **Generative Fill:** Seamlessly add or remove objects, transform backgrounds with descriptive text.
            * **Product Shot Tools:** Instant professional packshots, dynamic shadows, and immersive lifestyle scenes.
            * **Portrait Reimagine:** Explore diverse styles and settings for compelling portraits.
            * **Advanced Upscaling:** Enhance image resolution without losing quality.
            * **_And more powerful features being integrated!_**
            """
        )

        st.markdown("---")

        # Call to Action / Community Block
        st.subheader(" Got an Idea? Let's Connect!")
        st.info("Ready to turn your vision into reality? Explore the app, or reach out through !")
        st.markdown(
            """
            * [Github](https://github.com/Ananya-R2004) 
            * [LinkedIn](https://www.linkedin.com/in/ananya-r-a7b57b2a4/) 

            """
        )

        # Contact Info / Support
        st.markdown("---")
        st.subheader(" Support")
        st.markdown(
            """
            Need assistance? 
            * Email: [ananyarajesh2112@gmail.com](mailto:ananyarajesh2112@gmail.com)
            """
        )


        # 🧠 Brand/Project Promo Block
        st.markdown(
            """
            <div class="promo-block">
                <strong style="color:#FF6F61;">👑 Powered by AR Studio</strong><br>
                Crafted for creators, by creators.<br>
                <em>Redefining visual storytelling — one pixel at a time.</em>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Footer
        st.markdown("<p class='footer-text'>Developed with by Ananya R ", unsafe_allow_html=True)
        st.markdown("<p class='footer-text'>© 2025 AR Studio. All rights reserved.</p>", unsafe_allow_html=True)



    # Main tabs
    tabs = st.tabs([
    "🎨 Generate Image",
    "🖼️ Lifestyle Shot",
    "🎨 Generative Fill",
    "📦 Product Cutout",
    "🌄 Image Background Features",
    "✨ Image Editing Feature",
    "📸 Image Expansion"
])
    
    # --- CHATBOT INTEGRATION CODE ---

    components.html("""
        <style>
        /* Container for the floating chatbot popup */
        #chatbot-container {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 360px;
            height: 640px;
            z-index: 9999;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            border-radius: 15px;
            overflow: hidden;
        }
        zapier-interfaces-chatbot-embed {
            width: 100% !important;
            height: 100% !important;
            border-radius: 15px;
        }
    </style>
    <script async type='module' src='https://interfaces.zapier.com/assets/web-components/zapier-interfaces/zapier-interfaces.esm.js'></script>
    <div id="chatbot-container">
        <zapier-interfaces-chatbot-embed is-popup='true' chatbot-id='cme1qin6w001cbxros7z6roau'></zapier-interfaces-chatbot-embed>
    </div>
""", height=700, scrolling=False)
# --- END CHATBOT CODE ---

    # Generate Images Tab
    with tabs[0]:
        st.header("🎨 Generate Images")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            # Prompt input
            prompt = st.text_area("Enter your prompt", 
                                  value=st.session_state.original_prompt, # Use session state for persistence
                                  height=100,
                                  key="prompt_input")
            
            # Update original_prompt in session state when it changes
            if prompt != st.session_state.original_prompt:
                st.session_state.original_prompt = prompt
                st.session_state.enhanced_prompt = None  # Reset enhanced prompt when original changes
            
            # Enhanced prompt display
            if st.session_state.get('enhanced_prompt'):
                st.markdown("**Enhanced Prompt:**")
                st.markdown(f"*{st.session_state.enhanced_prompt}*")
            
            # Enhance Prompt button
            if st.button("✨ Enhance Prompt", key="enhance_button"):
                if not prompt:
                    st.warning("Please enter a prompt to enhance.")
                else:
                    with st.spinner("Enhancing prompt..."):
                        try:
                            # Assuming enhance_prompt now takes API key if needed, or uses a global one
                            # Changed based on your last code which passed st.session_state.api_key
                            result_prompt = enhance_prompt(st.session_state.api_key, prompt) 
                            if result_prompt: # Check if result_prompt is not empty/None
                                st.session_state.enhanced_prompt = result_prompt
                                st.success("Prompt enhanced!")
                                st.experimental_rerun()  # Rerun to update the display
                            else:
                                st.error("No enhanced prompt returned from the API.")
                        except Exception as e:
                            st.error(f"Error enhancing prompt: {str(e)}")
                            
        with col2:
            num_images = st.slider("Number of images", 1, 4, 1)
            aspect_ratio = st.selectbox("Aspect ratio", ["1:1", "16:9", "9:16", "4:3", "3:4"])
            enhance_img = st.checkbox("Enhance image quality", value=True)
            
            # Style options
            st.subheader("Style Options")
            style = st.selectbox("Image Style", [
                "Realistic", "Artistic", "Cartoon", "Sketch", 
                "Watercolor", "Oil Painting", "Digital Art"
            ])
            
        # Generate button
        if st.button("🎨 Generate Images", type="primary"):
            if not st.session_state.api_key:
                st.error("Please set your API key in the sidebar.")
                return
            
            current_prompt_to_use = st.session_state.enhanced_prompt if st.session_state.get('enhanced_prompt') else prompt
            if not current_prompt_to_use:
                st.warning("Please enter a prompt or enhance it first.")
                return

            # Add style to prompt if not Realistic
            final_prompt_with_style = current_prompt_to_use
            if style and style != "Realistic":
                final_prompt_with_style = f"{current_prompt_to_use}, in {style.lower()} style"
                
            with st.spinner("🎨 Generating your masterpiece..."):
                try:
                    # Pass API key to generate_hd_image
                    results_dict = generate_hd_image( # Renamed variable to reflect it's a dict
                        prompt=final_prompt_with_style,
                        api_key=st.session_state.api_key, # Explicitly pass API key
                        num_results=num_images,
                        aspect_ratio=aspect_ratio,
                        sync=True, 
                        enhance_image=enhance_img,
                        medium="art" if style != "Realistic" else "photography",
                        prompt_enhancement=False, # We're doing our own enhancement
                        content_moderation=True
                    )
                    
                    if results_dict and isinstance(results_dict, dict) and "result" in results_dict:
                        st.write("Debug - Raw API Response (Generate Images):", results_dict) # Keep for debugging
                        
                        image_urls_to_display = []
                        for item in results_dict["result"]:
                            if isinstance(item, dict) and "urls" in item and isinstance(item["urls"], list):
                                image_urls_to_display.extend(item["urls"])
                            # Add other potential patterns if the API can return them
                            elif isinstance(item, str) and item.startswith("http"): # If 'result' directly contains URLs
                                image_urls_to_display.append(item)


                        if image_urls_to_display:
                            st.success(f"✨ Image(s) generated successfully! Displaying {len(image_urls_to_display)} result(s).")
                            for i, bria_temp_url in enumerate(image_urls_to_display):
                                if bria_temp_url:
                                    local_path = download_and_save_temp_image(bria_temp_url, prefix=f"generated_img_{i}_")
                                    if local_path:
                                        st.image(local_path, caption=f"Generated Image {i+1}", use_container_width=True)
                                    else:
                                        st.warning(f"❌ Failed to download generated image {i+1} from URL: {bria_temp_url}.")
                                else:
                                    st.warning(f"❌ Bria.ai returned an empty URL for generated image {i+1}.")
                        else:
                            st.error("❌ No image URLs found in the API response after parsing.")
                    else:
                        st.error(f"❌ Unexpected response format from generate_hd_image. Expected a dictionary with 'result' key. Got: {type(results_dict)}")
                        st.write("Raw response:", results_dict)
                        
                except Exception as e:
                    st.error(f"❌ Error generating images: {str(e)}")
                    st.write("Full error:", str(e))

    # Product Photography Tab
    with tabs[1]:
        st.header("✨ Product Shot Tools")
        st.markdown("Generate professional product packshots, add shadows, or create lifestyle scenes.")

        product_tool_options = ["Product Packshot", "Product Shadow", "Lifestyle Product Shot by Text"]
        selected_tool = st.selectbox("Select a Product Tool:", product_tool_options)

        uploaded_product_file = st.file_uploader("Upload Product Image", type=["png", "jpg", "jpeg"], key="product_tool_upload")
        product_image_bytes = None
        if uploaded_product_file:
            product_image_bytes = uploaded_product_file.getvalue()
            st.image(uploaded_product_file, caption="Uploaded Product Image", use_container_width=True)

        # Common SKU input
        sku_input = st.text_input("SKU (Optional)", help="Stock Keeping Unit identifier for the product.")

        # --- Product Packshot Section ---
        if selected_tool == "Product Packshot":
            st.subheader("Product Packshot Generator")
            packshot_bg_color = st.color_picker("Background Color", "#FFFFFF", help="Hex color code for the background. 'transparent' is not supported via color picker but you can type it if allowed by API.")
            packshot_force_rmbg = st.checkbox("Force Background Removal", False, help="Forces background removal, even if image has alpha channel.")
            packshot_content_moderation = st.checkbox("Enable Content Moderation (Packshot)", False)

            if st.button("Generate Packshot", type="primary"):
                if not product_image_bytes:
                    st.error("Please upload a product image.")
                else:
                    with st.spinner("Generating Product Packshot..."):
                        result = create_product_packshot(
                            api_key=st.session_state.api_key,
                            image_bytes=product_image_bytes,
                            sku=sku_input if sku_input else None,
                            background_color=packshot_bg_color,
                            force_rmbg=packshot_force_rmbg,
                            content_moderation=packshot_content_moderation
                        )
                        if result and "result_url" in result:
                            st.session_state.packshot_image = result["result_url"]
                            st.success("Packshot generated successfully!")
                        elif result and "error" in result:
                            st.error(f"Packshot generation failed: {result['error']}")
                        else:
                            st.error("Failed to generate packshot. Unexpected API response.")

            if st.session_state.packshot_image:
                st.image(st.session_state.packshot_image, caption="Generated Packshot", use_container_width=True)
                packshot_data = download_image(st.session_state.packshot_image)
                if packshot_data:
                    st.download_button(
                        "⬇️ Download Packshot",
                        packshot_data,
                        "product_packshot.png",
                        "image/png"
                    )
                    # Save locally as well
                    local_path = download_and_save_temp_image(st.session_state.packshot_image, directory="temp_bria_results", prefix="packshot_")
                    if local_path:
                        st.info(f"Packshot saved locally to: `{local_path}`")


        # --- Product Shadow Section ---
        elif selected_tool == "Product Shadow":
            st.subheader("Add Product Shadow")
            shadow_type = st.radio("Shadow Type", ["regular", "float"], index=0)
            shadow_bg_color = st.color_picker("Background Color (Shadow)", "#FFFFFF", help="Hex color code for the background. Leave blank for transparent. This color picker defaults to white. You might need to add a checkbox for transparent or offer a text input for 'transparent'.")
            # Example for transparent background option
            use_transparent_shadow_bg = st.checkbox("Use Transparent Background for Shadow", False)
            if use_transparent_shadow_bg:
                shadow_bg_color = None # Set to None for transparent

            shadow_color = st.color_picker("Shadow Color", "#000000")
            shadow_offset_x = st.number_input("Shadow Offset X", value=0, help="Horizontal offset in pixels (can be negative).")
            shadow_offset_y = st.number_input("Shadow Offset Y", value=15, help="Vertical offset in pixels (can be negative).")
            shadow_intensity = st.slider("Shadow Intensity", 0, 100, 60)
            shadow_blur = st.number_input("Shadow Blur", value=15 if shadow_type == "regular" else 20, help="Controls the blur level of the shadow's edges.")

            if shadow_type == "float":
                shadow_width = st.number_input("Shadow Width (Float)", value=0, help="Controls the width of the elliptical shadow (pixels).")
                shadow_height = st.number_input("Shadow Height (Float)", value=70, help="Controls the height of the elliptical shadow (pixels).")
            else:
                shadow_width = None
                shadow_height = None

            shadow_force_rmbg = st.checkbox("Force Background Removal (Shadow)", False)
            preserve_alpha = st.checkbox("Preserve Alpha Channel", True, help="Retain original transparency if input has alpha channel.")
            shadow_content_moderation = st.checkbox("Enable Content Moderation (Shadow)", False)

            if st.button("Add Shadow", type="primary"):
                if not product_image_bytes:
                    st.error("Please upload a product image (preferably a cutout with transparent background).")
                else:
                    with st.spinner("Adding Shadow..."):
                        result = add_product_shadow(
                            api_key=st.session_state.api_key,
                            image_bytes=product_image_bytes,
                            sku=sku_input if sku_input else None,
                            shadow_type=shadow_type,
                            background_color=shadow_bg_color,
                            shadow_color=shadow_color,
                            shadow_offset=[shadow_offset_x, shadow_offset_y],
                            shadow_intensity=shadow_intensity,
                            shadow_blur=shadow_blur if shadow_blur is not None else (15 if shadow_type == "regular" else 20),
                            shadow_width=shadow_width,
                            shadow_height=shadow_height,
                            force_rmbg=shadow_force_rmbg,
                            preserve_alpha=preserve_alpha,
                            content_moderation=shadow_content_moderation
                        )
                        if result and "result_url" in result:
                            st.session_state.shadow_image = result["result_url"]
                            st.success("Shadow added successfully!")
                        elif result and "error" in result:
                            st.error(f"Shadow addition failed: {result['error']}")
                        else:
                            st.error("Failed to add shadow. Unexpected API response.")

            if st.session_state.shadow_image:
                st.image(st.session_state.shadow_image, caption="Image with Shadow", use_container_width=True)
                shadow_data = download_image(st.session_state.shadow_image)
                if shadow_data:
                    st.download_button(
                        "⬇️ Download Shadow Image",
                        shadow_data,
                        "product_with_shadow.png",
                        "image/png"
                    )
                    local_path = download_and_save_temp_image(st.session_state.shadow_image, directory="temp_bria_results", prefix="shadow_")
                    if local_path:
                        st.info(f"Shadow image saved locally to: `{local_path}`")

        # --- Lifestyle Product Shot by Text Section ---
        elif selected_tool == "Lifestyle Product Shot by Text":
            st.subheader("Lifestyle Product Shot by Text")
            scene_description = st.text_area("Scene Description", help="Describe the new scene/background for the product.")
            lifestyle_sync_mode = st.checkbox("Synchronous Mode (Lifestyle)", False, help="Wait for results immediately. Recommended for single result. For multiple results, use async (false).")
            lifestyle_fast_mode = st.checkbox("Fast Mode", True, help="Provides best balance between speed and quality.")
            optimize_description = st.checkbox("Optimize Description (Llama 3)", True)
            num_results_lifestyle = st.slider("Number of Variations", 1, 4, 1, disabled=lifestyle_sync_mode) # Max 1 if sync is True
            if num_results_lifestyle > 1 and lifestyle_sync_mode:
                st.warning("Synchronous mode only supports 1 result. Switching to 1 result.")
                num_results_lifestyle = 1
                lifestyle_sync_mode = False # Force async if multiple results selected

            exclude_elements = st.text_input("Exclude Elements (Optional)", help="Elements to exclude from the generated scene. Only for Fast Mode: False.")

            st.markdown("---")
            st.subheader("Placement Options")
            placement_type = st.selectbox(
                "Placement Type",
                ["original", "automatic", "manual_placement", "custom_coordinates", "manual_padding", "automatic_aspect_ratio"],
                index=0
            )

            current_aspect_ratio = None
            current_shot_size = None
            current_foreground_image_size = None
            current_foreground_image_location = None
            current_manual_placement_selection = None
            current_padding_values = None
            current_original_quality = False

            if placement_type == "original":
                current_original_quality = st.checkbox("Original Quality", False, help="Retain original input image size.")
            elif placement_type == "automatic":
                num_results_lifestyle = st.slider("Number of Variations (Automatic)", 1, 4, 1) # Automatic generates multiple by default
                lifestyle_sync_mode = False # Automatic always async
                st.info("Automatic placement generates multiple variations and operates in asynchronous mode.")
                current_shot_size = st.text_input("Shot Size (e.g., 1000,1000)", value="1000,1000")
            elif placement_type == "manual_placement":
                manual_placement_options = ["upper_left", "upper_right", "bottom_left", "bottom_right", "right_center", "left_center", "upper_center", "bottom_center", "center_vertical", "center_horizontal"]
                current_manual_placement_selection = st.multiselect("Select Placements", manual_placement_options, default=["center_horizontal"])
                current_shot_size = st.text_input("Shot Size (e.g., 1000,1000)", value="1000,1000")
            elif placement_type == "custom_coordinates":
                fg_img_width = st.number_input("Foreground Image Width", min_value=1, value=500)
                fg_img_height = st.number_input("Foreground Image Height", min_value=1, value=500)
                current_foreground_image_size = [fg_img_width, fg_img_height]
                fg_img_loc_x = st.number_input("Foreground Image Location X", value=0)
                fg_img_loc_y = st.number_input("Foreground Image Location Y", value=0)
                current_foreground_image_location = [fg_img_loc_x, fg_img_loc_y]
                current_shot_size = st.text_input("Shot Size (e.g., 1000,1000)", value="1000,1000")
            elif placement_type == "manual_padding":
                padding_left = st.number_input("Padding Left", value=0)
                padding_right = st.number_input("Padding Right", value=0)
                padding_top = st.number_input("Padding Top", value=0)
                padding_bottom = st.number_input("Padding Bottom", value=0)
                current_padding_values = [padding_left, padding_right, padding_top, padding_bottom]
            elif placement_type == "automatic_aspect_ratio":
                current_aspect_ratio = st.selectbox("Aspect Ratio", ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9"], index=0)

            lifestyle_force_rmbg = st.checkbox("Force Background Removal (Lifestyle)", False)
            lifestyle_content_moderation = st.checkbox("Enable Content Moderation (Lifestyle)", False)

            if st.button("Generate Lifestyle Shot", type="primary"):
                if not product_image_bytes:
                    st.error("Please upload a product image.")
                elif not scene_description:
                    st.error("Please provide a scene description.")
                else:
                    parsed_shot_size = None
                    if current_shot_size:
                        try:
                            parsed_shot_size = [int(x.strip()) for x in current_shot_size.split(',')]
                            if len(parsed_shot_size) != 2:
                                raise ValueError
                        except ValueError:
                            st.error("Invalid Shot Size format. Please use 'width,height' (e.g., 1000,1000).")
                            return

                    with st.spinner("Generating Lifestyle Shot..."):
                        result = create_lifestyle_shot_by_text(
                            api_key=st.session_state.api_key,
                            image_bytes=product_image_bytes,
                            scene_description=scene_description,
                            sku=sku_input if sku_input else None,
                            sync=lifestyle_sync_mode,
                            fast=lifestyle_fast_mode,
                            optimize_description=optimize_description,
                            num_results=num_results_lifestyle,
                            exclude_elements=exclude_elements if exclude_elements else None,
                            placement_type=placement_type,
                            original_quality=current_original_quality,
                            aspect_ratio=current_aspect_ratio,
                            shot_size=parsed_shot_size,
                            foreground_image_size=current_foreground_image_size,
                            foreground_image_location=current_foreground_image_location,
                            manual_placement_selection=current_manual_placement_selection,
                            padding_values=current_padding_values,
                            force_rmbg=lifestyle_force_rmbg,
                            content_moderation=lifestyle_content_moderation
                        )

                        if result and "result" in result:
                            st.success("Lifestyle shot generation initiated!")
                            # Clear previous results and pending URLs
                            st.session_state.lifestyle_images = []
                            st.session_state.pending_lifestyle_urls = []

                            for item in result["result"]:
                                if isinstance(item, list) and len(item) > 0:
                                    url = item[0]
                                    if url: # Check if URL is not empty/null (e.g., in case of moderation block)
                                        if lifestyle_sync_mode:
                                            st.session_state.lifestyle_images.append(url)
                                        else:
                                            st.session_state.pending_lifestyle_urls.append(url)
                                    else:
                                        st.warning(f"Skipping blocked or invalid result: {item}")
                                else:
                                    st.warning(f"Skipping invalid result item: {item}")

                            if lifestyle_sync_mode:
                                if st.session_state.lifestyle_images:
                                    st.success("All lifestyle images are ready!")
                                else:
                                    st.warning("No images returned in synchronous mode. Check API response for errors.")
                            elif st.session_state.pending_lifestyle_urls:
                                st.info(f"Asynchronous generation started. Waiting for {len(st.session_state.pending_lifestyle_urls)} image(s)...")
                                # Trigger a rerun or offer a refresh button for async
                                # For simple demo, we'll just show the pending info
                        elif result and "error" in result:
                            st.error(f"Lifestyle shot generation failed: {result['error']}")
                        else:
                            st.error("Failed to generate lifestyle shot. Unexpected API response.")

            # Display Lifestyle results
            if st.session_state.lifestyle_images:
                st.subheader("Generated Lifestyle Shots")
                for i, img_url in enumerate(st.session_state.lifestyle_images):
                    st.image(img_url, caption=f"Lifestyle Shot {i+1}", use_container_width=True)
                    lifestyle_data = download_image(img_url)
                    if lifestyle_data:
                        st.download_button(
                            f"⬇️ Download Lifestyle Shot {i+1}",
                            lifestyle_data,
                            f"lifestyle_shot_{i+1}.png",
                            "image/png"
                        )
                        local_path = download_and_save_temp_image(img_url, directory="temp_bria_results", prefix=f"lifestyle_{i+1}_")
                        if local_path:
                            st.info(f"Lifestyle image saved locally to: `{local_path}`")
            elif st.session_state.pending_lifestyle_urls:
                st.info("Lifestyle generation in progress. The images will appear here once ready.")
                # You might want to add a refresh button for asynchronous results here as well
                if st.button("Check Lifestyle Generation Status"):
                    # In a real app, you'd poll the API or check for file existence
                    # For this demo, we'll simulate them becoming ready
                    if st.session_state.pending_lifestyle_urls:
                        st.session_state.lifestyle_images.extend(st.session_state.pending_lifestyle_urls)
                        st.session_state.pending_lifestyle_urls = []
                        st.rerun() # Rerun to display the images
                    else:
                        st.info("No pending lifestyle images to check.")
    
    # Generative Fill Tab
    with tabs[2]:
     st.header("🎨 Generative Fill")
     st.markdown("Draw a mask on the image and describe what you want to generate in that area.")

     uploaded_file = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg"], key="fill_upload")
     if uploaded_file:
        # Create columns for original image and canvas
        col1, col2 = st.columns(2)

        with col1:
            # Display original image
            st.image(uploaded_file, caption="Original Image", use_container_width=True)

            # Get image dimensions for canvas
            img = Image.open(uploaded_file)
            img_width, img_height = img.size

            # Calculate aspect ratio and set canvas height
            aspect_ratio = img_height / img_width
            canvas_width = min(img_width, 800)  # Max width of 800px
            canvas_height = int(canvas_width * aspect_ratio)

            # Resize image to match canvas dimensions
            img = img.resize((canvas_width, canvas_height))

            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Convert to numpy array with proper shape and type
            img_array = np.array(img).astype(np.uint8)

            # Add drawing canvas using Streamlit's drawing canvas component
            stroke_width = st.slider("Brush width", 1, 50, 20)
            stroke_color = st.color_picker("Brush color", "#fff")
            drawing_mode = "freedraw"

            # Create canvas with background image
            canvas_result = st_canvas(
                fill_color="rgba(255, 255, 255, 0.0)",  # Transparent fill
                stroke_width=stroke_width,
                stroke_color=stroke_color,
                drawing_mode=drawing_mode,
                background_color="",  # Transparent background
                background_image=img if img_array.shape[-1] == 3 else None,  # Only pass RGB images
                height=canvas_height,
                width=canvas_width,
                key="canvas",
            )

            # Options for generation
            st.subheader("Generation Options")
            prompt = st.text_area("Describe what to generate in the masked area")
            negative_prompt = st.text_area("Describe what to avoid (optional)")

            col_a, col_b = st.columns(2)
            with col_a:
                num_results = st.slider("Number of variations", 1, 4, 1)
                sync_mode = st.checkbox("Synchronous Mode", False,
                                        help="Wait for results instead of getting URLs immediately",
                                        key="gen_fill_sync_mode")

            with col_b:
                seed = st.number_input("Seed (optional)", min_value=0, value=0,
                                       help="Use same seed to reproduce results")
                content_moderation = st.checkbox("Enable Content Moderation", False,
                                                 key="gen_fill_content_mod")

            if st.button("🎨 Generate", type="primary"):
                if not prompt:
                    st.error("Please enter a prompt describing what to generate.")
                    return

                if canvas_result.image_data is None:
                    st.error("Please draw a mask on the image first.")
                    return

                # Convert canvas result to mask
                mask_img = Image.fromarray(canvas_result.image_data.astype('uint8'), mode='RGBA')
                mask_img = mask_img.convert('L')

                # Convert mask to bytes
                mask_bytes = io.BytesIO()
                mask_img.save(mask_bytes, format='PNG')
                mask_bytes = mask_bytes.getvalue()

                # Convert uploaded image to bytes
                image_bytes = uploaded_file.getvalue()

                with st.spinner("🎨 Generating..."):
                    try:
                        result = generative_fill(
                            st.session_state.api_key,
                            image_bytes,
                            mask_bytes,
                            prompt,
                            negative_prompt=negative_prompt if negative_prompt else None,
                            num_results=num_results,
                            sync=sync_mode,
                            seed=seed if seed != 0 else None,
                            content_moderation=content_moderation
                        )

                        if result:
                            st.write("Debug - API Response:", result)

                            if sync_mode:
                                if "urls" in result and result["urls"]:
                                    st.session_state.edited_image = result["urls"][0]
                                    if len(result["urls"]) > 1:
                                        st.session_state.generated_images = result["urls"]
                                    st.success("✨ Generation complete!")
                                elif "result_url" in result:
                                    st.session_state.edited_image = result["result_url"]
                                    st.success("✨ Generation complete!")
                            else:
                                if "urls" in result:
                                    st.session_state.pending_urls = result["urls"][:num_results]

                                    # Create containers for status
                                    status_container = st.empty()
                                    refresh_container = st.empty()

                                    # Show initial status
                                    status_container.info(f"🎨 Generation started! Waiting for {len(st.session_state.pending_urls)} image{'s' if len(st.session_state.pending_urls) > 1 else ''}...")

                                    # Try automatic checking
                                    if auto_check_images(status_container):
                                        st.rerun()

                                    # Add refresh button
                                    if refresh_container.button("🔄 Check for Generated Images"):
                                        if check_generated_images():
                                            status_container.success("✨ Images ready!")
                                            st.rerun()
                                        else:
                                            status_container.warning("⏳ Still generating... Please check again in a moment.")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
                        st.write("Full error details:", str(e))

        with col2:
            # Display the primary generated image if available
            if st.session_state.edited_image:
                st.image(st.session_state.edited_image, caption="Generated Result", use_container_width=True)
                image_data = download_image(st.session_state.edited_image)
                if image_data:
                    st.download_button(
                        "⬇️ Download Result",
                        image_data,
                        "generated_fill.png",
                        "image/png"
                    )
            # Display multiple generated images if available (from async or multiple results)
            elif st.session_state.generated_images:
                st.subheader("Generated Variations")
                for i, img_url in enumerate(st.session_state.generated_images):
                    st.image(img_url, caption=f"Variation {i+1}", use_container_width=True)
                    
                    # **INTEGRATION POINT FOR `download_save_temp_image`**
                    # Download and save the image locally
                    local_path = download_and_save_temp_image(img_url, directory="temp_bria_results", prefix="generative_fill_")
                    if local_path:
                        st.write(f"Image saved locally to: `{local_path}`")
                        # You could potentially offer a download button for the local file here too,
                        # but typically, Streamlit download button works directly with bytes from URL.
                        # For local file, you'd read its bytes.
                        with open(local_path, "rb") as file:
                            st.download_button(
                                label=f"Download Variation {i+1}",
                                data=file.read(),
                                file_name=os.path.basename(local_path),
                                mime="image/png"
                            )

            elif st.session_state.pending_urls:
                st.info("Generation in progress. Click the refresh button above to check status.")

    # Product Cutout Tab
    with tabs[3]:
       st.header("📦 Product Cutout")

       image_url = st.text_input("Enter the image URL of your product:")
       sku = st.text_input("Optional SKU (Stock Keeping Unit):", value="demo-sku")

       if st.button("✂️ Cut Out Product"):
         if image_url:
             with st.spinner("Processing image..."):
                 result_url = product_cutout(image_url=image_url, sku=sku)
                 if result_url:
                    st.success("✅ Product cutout successful!")
                    st.image(result_url, caption="Cutout Result", use_container_width=True)
                 else:
                    st.error("❌ Failed to process the image.")
       else:
            st.warning("⚠️ Please provide a valid image URL.")

    with tabs[4]:
        st.header("🌄 Image Background Features")
        image_url_bg_features = st.text_input("Enter the image URL for background features:", key="bg_features_image_url")
        
        # Sub-tabs for each background feature
        sub_tab_titles = ["Generate Background", "Remove Background", "Blur Background"]
        sub_tabs = st.tabs(sub_tab_titles)

        # Generate Background Section
        with sub_tabs[0]:
            st.subheader("Generate Background")
            bg_prompt = st.text_input("Enter a prompt for the new background (e.g., 'in a futuristic city', '#FF0000' for red)", key="generate_bg_prompt")
            num_results = st.slider("Number of results (only 1 if sync is True):", 1, 4, 1, key="generate_bg_num_results")
            use_fast_mode = st.checkbox("Use Fast Mode (Optimal balance between speed and quality)", value=True, key="generate_bg_fast")
            
            if st.button("🖼️ Generate New Background", key="generate_bg_button"):
                if image_url_bg_features and bg_prompt:
                    with st.spinner("Generating new background..."):
                        try:
                            # Note: Bria's /background/replace with sync=True and num_results > 1 can be tricky.
                            # For simplicity, if num_results > 1, we force sync=False and inform the user.
                            # For the UI, we will only display the first result for now.
                            sync_mode = True # Default to sync for single result display
                            if num_results > 1:
                                sync_mode = False # Force async if multiple results are requested
                                st.info("For multiple results, the API will run asynchronously. Only the first result will be displayed here immediately.")

                            bria_temp_url = generate_background(
                                image_url=image_url_bg_features,
                                bg_prompt=bg_prompt,
                                num_results=num_results,
                                sync=sync_mode, # Pass the determined sync_mode
                                fast=use_fast_mode
                            )
                            
                            if bria_temp_url:
                                local_image_path = download_and_save_temp_image(bria_temp_url, prefix="gen_bg_")
                                if local_image_path:
                                    st.success("✅ Background generated successfully!")
                                    st.image(local_image_path, caption=f"Generated Background: '{bg_prompt}'", use_container_width=True)
                                else:
                                    st.error("❌ Failed to download the generated image.")
                            else:
                                st.error("❌ Failed to get a result URL from Bria.ai.")
                        except (ValueError, requests.exceptions.RequestException, RuntimeError) as e:
                            st.error(f"❌ Error during background generation: {e}")
                else:
                    st.warning("⚠️ Please provide an image URL and a background prompt.")

        # Remove Background Section
        with sub_tabs[1]:
            st.subheader("Remove Background")
            preserve_alpha_rmbg = st.checkbox("Preserve partial alpha (for smooth edges)", value=True, key="remove_bg_preserve_alpha")
            
            if st.button("✂️ Remove Background", key="remove_bg_button"):
                if image_url_bg_features:
                    with st.spinner("Removing background..."):
                        try:
                            bria_temp_url = remove_image_background(
                                image_url=image_url_bg_features,
                                preserve_partial_alpha=preserve_alpha_rmbg,
                                sync=True # Always sync for direct display in Streamlit
                            )
                            if bria_temp_url:
                                local_image_path = download_and_save_temp_image(bria_temp_url, prefix="removed_bg_")
                                if local_image_path:
                                    st.success("✅ Background removed successfully!")
                                    st.image(local_image_path, caption="Background Removed", use_container_width=True)
                                else:
                                    st.error("❌ Failed to download the processed image.")
                            else:
                                st.error("❌ Failed to get a result URL from Bria.ai.")
                        except (ValueError, requests.exceptions.RequestException, RuntimeError) as e:
                            st.error(f"❌ Error during background removal: {e}")
                else:
                    st.warning("⚠️ Please provide an image URL.")

        # Blur Background Section
        with sub_tabs[2]:
            st.subheader("Blur Background")
            blur_scale = st.slider("Blur Scale (1: least blur, 5: most blur):", 1, 5, 5, key="blur_bg_scale")
            preserve_alpha_blur = st.checkbox("Preserve alpha (if input has transparency)", value=True, key="blur_bg_preserve_alpha")
            
            if st.button("🌫️ Blur Background", key="blur_bg_button"):
                if image_url_bg_features:
                    with st.spinner("Blurring background..."):
                        try:
                            bria_temp_url = blur_background(
                                image_url=image_url_bg_features,
                                scale=blur_scale,
                                preserve_alpha=preserve_alpha_blur,
                                sync=True # Always sync for direct display in Streamlit
                            )
                            if bria_temp_url:
                                local_image_path = download_and_save_temp_image(bria_temp_url, prefix="blurred_bg_")
                                if local_image_path:
                                    st.success("✅ Background blurred successfully!")
                                    st.image(local_image_path, caption="Background Blurred", use_container_width=True)
                                else:
                                    st.error("❌ Failed to download the processed image.")
                            else:
                                st.error("❌ Failed to get a result URL from Bria.ai.")
                        except (ValueError, requests.exceptions.RequestException, RuntimeError) as e:
                            st.error(f"❌ Error during background blurring: {e}")
                else:
                    st.warning("⚠️ Please provide an image URL.")
        
    with tabs[5]: # Index is still 5 as no tabs were added/removed, only content changed
        st.header("✨ Image Editing Features")
        image_url_editing_features = st.text_input("Enter the image URL for editing features:", key="editing_features_image_url")
        
        # Only one sub-tab now: "Erase Foreground"
        # Removed sub_tab_titles_editing and sub_tabs_editing for simplicity if only one feature
        # If you prefer to keep it as a sub-tab structure for future additions, you can
        # sub_tab_titles_editing = ["Erase Foreground"]
        # sub_tabs_editing = st.tabs(sub_tab_titles_editing)
        # with sub_tabs_editing[0]:

        st.subheader("Erase Foreground")
        preserve_alpha_erase_fg = st.checkbox("Preserve alpha (for transparency after erase)", value=True, key="erase_fg_preserve_alpha")
        
        if st.button("🗑️ Erase Foreground", key="erase_fg_button"):
            if image_url_editing_features:
                with st.spinner("Erasing foreground..."):
                    try:
                        bria_temp_url = erase_foreground(
                            image_url=image_url_editing_features,
                            preserve_alpha=preserve_alpha_erase_fg,
                            sync=True
                        )
                        if bria_temp_url:
                            local_path = download_and_save_temp_image(bria_temp_url, prefix="erased_fg_")
                            if local_path:
                                st.success("✅ Foreground erased successfully!")
                                st.image(local_path, caption="Foreground Erased", use_container_width=True)
                            else:
                                st.error("❌ Failed to download the processed image.")
                        else:
                            st.error("❌ Failed to get a result URL from Bria.ai.")
                    except (ValueError, requests.exceptions.RequestException, RuntimeError) as e:
                        st.error(f"❌ Error during foreground erasing: {e}")
            else:
                st.warning("⚠️ Please provide an image URL.")
    
    with tabs[6]: # This index will be 6
        st.header("↔️ Image Expansion")
        image_url_expansion = st.text_input("Enter the image URL to expand:", key="expansion_image_url")
        
        st.subheader("Expansion Options")
        expansion_mode = st.radio(
            "Choose Expansion Mode:",
            ("Aspect Ratio", "Precise Control (Canvas Size & Original Image Position)"),
            key="expansion_mode"
        )

        prompt_expansion = st.text_area(
            "Optional: Prompt to guide expansion (e.g., 'a lush forest', 'more sky')",
            key="expansion_prompt"
        )
        
        preserve_alpha_expansion = st.checkbox(
            "Preserve alpha (if input has transparency)",
            value=True, key="expansion_preserve_alpha"
        )
        
        st.caption("Note: Images with full transparency at edges may cause errors for expansion.")

        payload_options = {}

        if expansion_mode == "Aspect Ratio":
            aspect_ratio_option = st.selectbox(
                "Select Aspect Ratio:",
                ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "Custom Float"],
                key="aspect_ratio_preset"
            )
            if aspect_ratio_option == "Custom Float":
                custom_aspect_ratio = st.number_input(
                    "Enter custom aspect ratio (e.g., 0.75 for 3:4, 1.5 for 3:2):",
                    min_value=0.5, max_value=3.0, value=1.0, step=0.01, format="%.2f",
                    key="custom_aspect_ratio"
                )
                payload_options["aspect_ratio"] = custom_aspect_ratio
            else:
                payload_options["aspect_ratio"] = aspect_ratio_option
        else: # Precise Control
            st.info("For Precise Control, you need to know your original image's dimensions to place it accurately on the new canvas.")
            col1, col2 = st.columns(2)
            with col1:
                canvas_width = st.number_input("Canvas Width:", min_value=100, max_value=5000, value=1500, key="canvas_width")
                original_img_width_precise = st.number_input("Original Image Width (within canvas):", min_value=1, max_value=5000, value=800, key="orig_img_width_precise")
                original_img_x_precise = st.number_input("Original Image X-position (top-left):", value=350, key="orig_img_x_precise")
            with col2:
                canvas_height = st.number_input("Canvas Height:", min_value=100, max_value=5000, value=1000, key="canvas_height")
                original_img_height_precise = st.number_input("Original Image Height (within canvas):", min_value=1, max_value=5000, value=600, key="orig_img_height_precise")
                original_img_y_precise = st.number_input("Original Image Y-position (top-left):", value=200, key="orig_img_y_precise")
            
            payload_options["canvas_size"] = [canvas_width, canvas_height]
            payload_options["original_image_size"] = [original_img_width_precise, original_img_height_precise]
            payload_options["original_image_location"] = [original_img_x_precise, original_img_y_precise]

        if st.button("✨ Expand Image", key="expand_image_button"):
            if image_url_expansion:
                with st.spinner("Expanding image..."):
                    try:
                        bria_temp_url = expand_image(
                            image_url=image_url_expansion,
                            prompt=prompt_expansion if prompt_expansion else None,
                            preserve_alpha=preserve_alpha_expansion,
                            sync=True,
                            **payload_options # Unpack the chosen options (aspect_ratio or precise control)
                        )
                        if bria_temp_url:
                            local_path = download_and_save_temp_image(bria_temp_url, prefix="expanded_")
                            if local_path:
                                st.success("✅ Image expanded successfully!")
                                st.image(local_path, caption="Expanded Image", use_container_width=True)
                            else:
                                st.error("❌ Failed to download the expanded image.")
                        else:
                            st.error("❌ Failed to get a result URL from Bria.ai.")
                    except (ValueError, requests.exceptions.RequestException, RuntimeError) as e:
                        st.error(f"❌ Error during image expansion: {e}")
            else:
                st.warning("⚠️ Please provide an image URL to expand.")


if __name__ == "__main__":
    main()