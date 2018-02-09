"""A mechanism for transferring style of art to content."""


class Stylizer(object):
	"""An algorithm for stylizing images based on artwork."""

	def __init__(self,
				 content_layer_name: str='block4_conv2',
				 content_weight: float=1.0,
				 style_layer_names: list=[
				 	'block1_conv1',
				 	'block2_conv1',
				 	'block3_conv1',
				 	'block4_conv1',
				 	'block5_conv1'
				 ],
				 style_weight: float=10000.0) -> None:
		"""
		Initialize a new stylizer.

		Args:
			content_layer_name: the name of the layer to extract content from
			content_weight: the weight to attribute to content loss
			style_layer_names: the names of the layers to extract style from
			style_weight: the weight to attribute to style loss

		Returns: None
		"""
		# TODO: type and value check parameters for errors
		self.content_layer_name = content_layer_name
		self.content_weight = content_weight
		self.style_layer_names = style_layer_names
		self.style_weight = style_weight

	@property
	def content_style_ratio(self) -> float:
		"""Return the ratio of content weight to style weight."""
		return self.content_weight / self.style_weight

	def _load_images(self, content_path: str, style_path: str) -> tuple:
		"""
		Load the content and style images from disk and normalize them.

		Args:
			content_path: the path to the content image
			style_path: the path to the style image

		Returns: a tuple of content, style numpy matrices
		"""
		# load the content with the given size or it's default size
		content = load_image(content_path, image_size)
		# reassign image size in case it was none before loading the style
		image_size = content.width, content.height
		# load the style as the same size as the content
		style = load_image(style_path, image_size)
		# convert to 4D matrices
		content = image_to_matrix(content)
		style = image_to_matrix(style)
		# normalize about the means of the ImageNet dataset
		content = normalize(content)
		style = normalize(style)

		return content, style

	def _build_model(self, content: np.ndarray, style: np.ndarray) -> VGG_19:
		"""
		Build a synthesis model with the given content and style.

		Args:
			content: the content to fuse the artwork into
			style: the artwork to get the style from

		Returns: the constructed VGG19 model from the input images
		"""
		# load the content image into keras as a constant, it never changes
		content_tensor = K.constant(content, name='Content')
		# load the style image into keras as a constant, it never changes
		style_tensor = K.constant(style, name='Style')
		# create a placeholder for the trained image, this variable changes
		canvas = K.placeholder(content.shape, name='Canvas')
		# combine the content, style, and canvas tensors along the frame
		# axis (0) into a 4D tensor of shape [3, height, width, channels]
		tensor = K.concatenate([content_tensor, style_tensor, canvas], axis=0)
		# build the model with the input tensor of content, style, and canvas
		model = VGG_19(include_top=False, input_tensor=tensor, pooling='avg')

		return model, canvas

	def _build_loss_grads(self, model, canvas):
		"""
		Build the optimization methods for stylizing the image from a model.

		Args:
			model: the model to extract layers from

		Returns: a function to calculate loss and gradients from an input X
		"""
		# initialize a variable to store the loss into
		loss = K.variable(0.0, name='Loss')

		# CONTENT LOSS
		# extract the content layer tensor for optimizing content loss
		content_layer_output = model[self.content_layer_name]
		# calculate the loss between the output of the layer on the
		# content (0) and the canvas (2)
		loss += self.content_weight * content_loss(content_layer_output[0],
											  	   content_layer_output[2])

		# STYLE LOSS
		# iterate over the list of all the layers that we want to include
		for style_layer_name in self.style_layers_names:
		    # extract the layer's out that we have interest in for
		    # reconstruction
		    style_layer_output = model[style_layer_name]
		    # calculate the loss between the output of the layer on the
		    # style (1) and the canvas (2).
		    loss_s = style_loss(style_layer_output[1], style_layer_output[2])
		    # Apply the lazy w_l factor of dividing by the size of the
		    # styling layer list. multiply the style weight in here
		    loss += loss_s * self.style_weight / len(self.style_layers_names)

		# TOTAL VARIATION LOSS
		# add the total variation loss based on the euclidean distance
		# between shifted points
		# loss += total_variation_weight * total_variation_loss(canvas)

		# GRADIENTS
		# calculate the gradients of the input image with respect to
		# the loss. i.e. backpropagate the loss through the network
		# to the input layer (only the canvas though)
		grads = K.gradients(loss, canvas)[0]

		# generate the iteration function for gradient descent optimization
		# Args:
		#     noise: the input to the noise placeholder in the model
		#         this effectively takes a the white noise image being
		#         optimized and passes it forward and backward through
		#         the model collecting the loss and gradient along the
		#         way
		#
		# Returns:
		#     a tuple of (loss, gradients)
		#     -   loss: the content loss between the content, style image
		#         and the white noise
		#     -   gradients: the gradients of the inputs with respect
		#         to the loss
		return K.function([canvas], [loss, grads])

	def stylilze(self,
				 content_path: str,
				 style_path: str,
				 optimizer,
				 image_size: tuple=None,
				 noise_range: tuple=(0, 1)):
		"""
		"""
		# load the images
		content, style = self._load_images(content_path, style_path)
		# build the inputs tensor from the images
		model, canvas = self._build_model(content, style)
		# build the iteration function
		loss_grads = self._build_loss_grads(model, canvas)
		# generate some white noise
		noise = np.random.uniform(*noise_range, content.shape)