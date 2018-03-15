import tensorflow as tf
import se3
import tools


# CNN Block
def cnn_model(inputs):
    conv6 = tf.contrib.layers.conv2d(inputs, num_outputs=1024, kernel_size=(3, 3,),
                                     stride=(2, 2), padding="same", scope="conv_6")
    return conv6


def fc_model(inputs):
    fc_128 = tf.contrib.layers.fully_connected(inputs, 128, scope="fc_128", activation_fn=tf.nn.relu)
    fc_12 = tf.contrib.layers.fully_connected(fc_128, 12, scope="fc_12", activation_fn=tf.nn.relu)
    return fc_12


def se3_comp_over_timesteps(fc_timesteps):
    initial_pose = [0, 0, 0,
                    1, 0, 0, 0]  # position + orientation in quat
    poses = tools.foldl(se3.se3_comp, fc_timesteps[:, 0:7], name="se3_comp_foldl",
                        initializer=tf.constant(initial_pose, dtype=tf.float32), dtype=tf.float32)
    return poses


def build_model(batch_size, max_timesteps):
    input_width = 40
    input_height = 12
    input_channels = 512

    input_data = tf.placeholder(tf.float32, name="input_data",
                                shape=[batch_size, max_timesteps, input_width, input_height, input_channels])

    with tf.variable_scope("CNN", reuse=tf.AUTO_REUSE):
        input_data = tf.unstack(input_data, axis=1)
        cnn_outputs = tf.map_fn(cnn_model, input_data, dtype=tf.float32, name="cnn_map")

    cnn_outputs = tf.reshape(cnn_outputs,
                             [batch_size, max_timesteps,
                              cnn_outputs.shape[2] * cnn_outputs.shape[3] * cnn_outputs.shape[4]])

    # RNN Block
    with tf.variable_scope("RNN"):
        lstm_cell_1 = tf.contrib.rnn.BasicLSTMCell(num_units=1024)
        lstm_cell_2 = tf.contrib.rnn.BasicLSTMCell(num_units=1024)
        layered_lstm_cell = tf.contrib.rnn.MultiRNNCell([lstm_cell_1, lstm_cell_2], state_is_tuple=True)
        rnn_outputs, _ = tf.nn.dynamic_rnn(layered_lstm_cell, cnn_outputs, dtype=tf.float32)

    with tf.variable_scope("Fully-Connected", reuse=tf.AUTO_REUSE):
        rnn_outputs = tf.unstack(rnn_outputs, axis=1)
        fc_outputs = tf.map_fn(fc_model, rnn_outputs, dtype=tf.float32, name="fc_map")

    with tf.variable_scope("SE3"):
        # at this point the outputs from the fully connected layer are  [x, y, z, yaw, pitch, roll, 6 x covars]
        # fc_outputs = tf.unstack(fc_outputs, axis=0)  # unstack the batches for processing along the timesteps
        se3_outputs = tf.map_fn(se3_comp_over_timesteps, fc_outputs, dtype=tf.float32, name="se3_map")

    return se3_outputs, fc_outputs
