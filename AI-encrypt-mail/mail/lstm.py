import numpy as np
import tensorflow as tf
import tensorflow_hub as hub


class LSTM():
    def __init__(self, lr, epochs, batch_size, nnlm='../data/nnlm-zh-dim50', max_length=256):
        # 模型参数
        self.model = tf.keras.Sequential()
        self.learning_rate = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.saved_model = None
        # 数据特征提取配置
        self.embed = hub.load(nnlm)
        self.max_length = max_length

    def get_embed(self, text: str):
        char_array = [c for c in text[:self.max_length]]
        _embed = self.embed(char_array).numpy()
        # padding 到最大长度
        diff = self.max_length - len(char_array)
        if diff > 0:
            _embed = np.pad(_embed, ((0, diff), (0, 0)))
        return _embed

    def load_data(self, data='../data/data_all.txt'):
        feature = []
        label = []
        samples = 0
        with open(data, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    samples += 1
                    parts = line.split('\t')
                    label.append(int(parts[0]))
                    feature.append(self.get_embed(parts[1].strip()))
        label_array = np.expand_dims(label, axis=1)
        return np.array(feature), label_array

    def build_lstm(self, lstm_dims=None, dense_dim=32):
        """根据输入的配置，构建双向 LSTM 网络，
            Args:
              lstm_dims: 每一层的 LSTM units 数量
              dense_dim: 最后决策层的权重矩阵 units
        """
        if lstm_dims is None:
            lstm_dims = [64]
        if len(lstm_dims) == 1:
            self.model.add(tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(lstm_dims[0])))
        else:
            for dim in lstm_dims[:-1]:
                self.model.add(tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(dim, return_sequences=True)))
            self.model.add(tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(lstm_dims[-1])))
        self.model.add(tf.keras.layers.Dense(dense_dim, activation='relu'))
        self.model.add(tf.keras.layers.Dense(1))
        loss_object = tf.keras.losses.BinaryCrossentropy(from_logits=True)
        optimizer = tf.keras.optimizers.Adam(learning_rate=self.learning_rate)
        self.model.compile(optimizer=optimizer, loss=loss_object,
                           metrics=[tf.keras.metrics.BinaryAccuracy(threshold=0)])

    def train(self, feature, label, saved_model='lstm'):
        train_num = int(len(feature) * 0.9)
        train_data, train_label = feature[0:train_num], label[0:train_num]
        test_data, test_label = feature[train_num:], label[train_num:]
        self.model.fit(train_data, train_label, epochs=self.epochs, batch_size=self.batch_size, shuffle=True,
                       validation_data=(test_data, test_label))
        self.model.save(saved_model)

    def test(self, test_data, test_label):
        loss, acc = self.saved_model.evaluate(test_data, test_label, verbose=1)
        print('Accuracy: {:5.2f}%'.format(100 * acc))

    def test_one(self, text, saved_model):
        _feature = np.array([self.get_embed(text)])
        if not self.saved_model:
            print('Loading saved model')
            if not saved_model:
                raise ValueError('Do not have a trained model, please train the model first')
            else:
                try:
                    self.saved_model = tf.keras.models.load_model(saved_model)
                except IOError as e:
                    print('Saved model file does not exist at: ' + saved_model)
                    raise e
        prediction = self.saved_model(_feature)
        score = np.squeeze(prediction.numpy())
        if score > 0:
            return 1
        else:
            return 0


if __name__ == '__main__':
    # 1. 建立 LSTM 网络
    lstm = LSTM(lr=1e-4, epochs=10, batch_size=100)
    # 加载训练数据
    feature, label = lstm.load_data('../data/data_all.txt')
    # 默认是一个 64 维的 BiLSTM cell
    lstm.build_lstm([32])
    lstm.train(feature, label, saved_model='lstm')

    # 2. 根据训练好的模型，预测是否为不良言论
    saved_lstm = LSTM(lr=1e-4, epochs=10, batch_size=100)
    text = '2022年报税发票代开，威尼斯商人带你玩转轮盘'
    result = saved_lstm.test_one(text, saved_model='lstm')
    print(result)
    text = '美国人自己的主流评论大约是阿甘,作为一部主旋律影片的确不错(我曾经喜欢死了),但是它毕竟只是一部流行电影!也也是为什么它“当年”可以获奖的原因了。'
    result = saved_lstm.test_one(text, saved_model='lstm')
    print(result)
