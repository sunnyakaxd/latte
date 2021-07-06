module.exports = {
    "root": true,
    "extends": "airbnb-base",
    "parserOptions": {
        "ecmaVersion": 8,
        "ecmaFeatures": {
            "jsx": true
        }
    },
    "rules": {
      "camelcase": 0,
      "consistent-return": 0,
      "no-case-declarations": 0,
      "max-len": 0,
      "no-continue": 0,
      "no-multi-assign": 0,
      "no-param-reassign": 0,
      "no-plusplus": 0,
      "no-restricted-syntax": ["error", "BinaryExpression[operator='in']"],
      "no-return-assign": 0,
      "no-underscore-dangle": 0,
      "no-use-before-define": 0,
      "prefer-rest-params": 0,
      "semi": 2,
    },
    "env": {
      "browser": true,
    },
    "globals": {
      "__": true,
      "$": true,
      "cur_frm": true,
      "cur_page": true,
      "document": true,
      "frappe": true,
      "has_common": true,
      "locals": true,
      "Slick": true,
      "window": true,
    }
}
